import os
import json
import time
import inspect
import logging
from datetime import datetime
from app.core.database import SessionLocal
from app.models.job import Job, JobStatus
from app.models.execution_log import AgentExecutionLog
from app.core.config import settings
from app.orchestrator.router import AgentRouter
from app.orchestrator.validator import ArtifactValidator
from app.services import credits as credit_service
from agents.reviewer import ReviewerAgent
from agents.memory import AgentMemoryStore
from agents.video.progress import stage as complete_stage
from app.services.thumbnail import extract_thumbnail

logger = logging.getLogger("uvicorn")

def run_job_workflow(job_id: str):
    """
    Executes the job workflow lifecycle asynchronously.
    Updates DB status from QUEUED -> RUNNING -> COMPLETED or FAILED,
    performing Artifact Validation, Reviewer Quality Evaluation, and Execution Logging.
    """
    db = SessionLocal()
    start_time = time.time()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error(f"Workflow error: Job {job_id} not found.")
            return

        job.status = JobStatus.RUNNING.value
        job.progress_percent = 5
        job.current_step = "Job workflow initialized"
        db.commit()

        agent = AgentRouter.get_agent(job.agent_type)

        target_dir = os.path.join(settings.STORAGE_PATH, job.id)
        os.makedirs(target_dir, exist_ok=True)

        def progress_callback(percent: int, step_desc: str):
            try:
                db.refresh(job)
                job.progress_percent = percent
                job.current_step = step_desc
                db.commit()
                logger.info(f"Job {job.id}: {percent}% -- {step_desc}")
            except Exception as pe:
                logger.error(f"Error updating progress callback: {pe}")

        # 1. Execute Agent Task
        exec_start = time.time()
        if job.agent_type.lower() in ("multiagent", "all"):
            from agents.presentation.agent import PresentationAgent
            from agents.latex.agent import LaTeXReportAgent
            from agents.video.agent import VideoAgent

            progress_callback(10, "Multi-Agent: Generating Presentation Deck (PPTX)...")
            p_agent = PresentationAgent()
            p_agent.execute(job.id, job.prompt)
            pptx_path = p_agent.generate_artifact(job.id, job.prompt, target_dir)

            progress_callback(40, "Multi-Agent: Generating Technical Report (PDF)...")
            l_agent = LaTeXReportAgent()
            l_agent.execute(job.id, job.prompt)
            pdf_path = l_agent.generate_artifact(job.id, job.prompt, target_dir)

            progress_callback(70, "Multi-Agent: Rendering High-Retention Video (MP4)...")
            v_agent = VideoAgent()
            v_agent.execute(job.id, job.prompt)
            mp4_path = v_agent.generate_artifact(job.id, job.prompt, target_dir)

            artifact_path = mp4_path
        else:
            # The job's UI settings (aspect ratio, length, voice, language, and the
            # report cover fields). Absent or malformed settings fall back to defaults.
            #
            # The column is still called video_options for historical reasons; it now
            # carries settings for every agent type, which is why the report language
            # travels in it too.
            agent_options = {}
            if getattr(job, "video_options", None):
                try:
                    agent_options = json.loads(job.video_options) or {}
                except (ValueError, TypeError) as e:
                    logger.warning(f"Job {job.id}: ignoring unreadable video_options ({e}).")

            # Pass only what each agent's signature actually declares.
            #
            # This used to be an if/elif that assumed an agent accepting progress_callback
            # also accepted options, and vice versa. The report agent -- which takes
            # options but not progress_callback -- fell through the gap, so the language
            # selector reached the API and then silently died here. Filtering on the real
            # signature means adding a parameter to any agent is enough to receive it.
            exec_params = inspect.signature(agent.execute).parameters
            exec_kwargs = {"progress_callback": progress_callback}
            if "options" in exec_params:
                exec_kwargs["options"] = agent_options
            agent.execute(job.id, job.prompt, **exec_kwargs)

            # generate_artifact is where the minutes actually go, so it -- not execute() --
            # has to drive the bar.
            gen_params = inspect.signature(agent.generate_artifact).parameters
            artifact_kwargs = {}
            if "options" in gen_params:
                artifact_kwargs["options"] = agent_options
            if "progress_callback" in gen_params:
                artifact_kwargs["progress_callback"] = progress_callback
            artifact_path = agent.generate_artifact(job.id, job.prompt, target_dir, **artifact_kwargs)

        exec_duration_ms = (time.time() - exec_start) * 1000.0

        # Log Execution Step in DB
        log_entry = AgentExecutionLog(
            job_id=job.id,
            agent_name=job.agent_type,
            step_name="artifact_generation",
            input_text=job.prompt[:200],
            output_text=artifact_path,
            execution_time_ms=exec_duration_ms,
            status="SUCCESS"
        )
        db.add(log_entry)
        db.commit()

        # 2. Validate Artifact Integrity
        if not ArtifactValidator.validate_artifact(artifact_path, job.agent_type):
            raise RuntimeError(f"Artifact validation failed for {artifact_path}")

        # 3. Reviewer Agent Quality Evaluation (Evaluator-Optimizer Loop)
        critique = ReviewerAgent.review_deliverable(job.agent_type, artifact_path, job.prompt)
        
        # Log Reviewer Step
        rev_log = AgentExecutionLog(
            job_id=job.id,
            agent_name="reviewer",
            step_name="quality_evaluation",
            input_text=artifact_path,
            output_text=f"Score: {critique.quality_score:.2f} | Approved: {critique.is_approved}",
            execution_time_ms=10.0,
            status="SUCCESS" if critique.is_approved else "WARNING"
        )
        db.add(rev_log)
        db.commit()

        # If quality score below threshold, attempt 1 revision retry pass
        if not critique.is_approved:
            logger.warning(f"Reviewer scored job {job.id} at {critique.quality_score:.2f}. Triggering self-correction pass...")
            # Built from the signature rather than reusing artifact_kwargs, which only
            # exists on the single-agent branch above.
            retry_kwargs = {}
            if "progress_callback" in inspect.signature(agent.generate_artifact).parameters:
                # Without this the bar freezes at the last reported stage for the whole
                # second render, then jumps to 100%.
                retry_kwargs["progress_callback"] = progress_callback
            artifact_path = agent.generate_artifact(
                job.id, f"{job.prompt}. Note: {critique.revision_instructions}", target_dir, **retry_kwargs
            )
            # The retry replaces the artifact, so it has to clear the same bar the first
            # one did. Without this a failed or truncated second render reaches COMPLETED
            # having never been validated at all.
            if not ArtifactValidator.validate_artifact(artifact_path, job.agent_type):
                raise RuntimeError(f"Artifact validation failed after self-correction pass for {artifact_path}")
            critique = ReviewerAgent.review_deliverable(job.agent_type, artifact_path, job.prompt)

        # 4. Record Job in Agent Memory
        AgentMemoryStore.record_job_execution(
            job_id=job.id,
            agent_type=job.agent_type,
            prompt=job.prompt,
            artifact_path=artifact_path,
            quality_score=critique.quality_score
        )

        # 5. Completion gate -- the single point where a job becomes COMPLETED.
        #
        # Re-checked here rather than trusting the validation above: that ran before the
        # reviewer pass, and on the retry path the file it approved is not the file being
        # delivered. This is the last read of the artifact before the UI is told it is
        # ready, so it is the only one whose result is still true afterwards.
        if not os.path.exists(artifact_path):
            raise RuntimeError(f"Refusing to complete: artifact vanished before completion ({artifact_path})")
        final_size = os.path.getsize(artifact_path)
        if final_size <= 0:
            raise RuntimeError(f"Refusing to complete: artifact is {final_size} bytes ({artifact_path})")

        # Poster frame for the dashboard card. Best-effort by design: the thumbnail is
        # decorative, so a failure here must not fail a job whose video is fine.
        if artifact_path.lower().endswith(".mp4"):
            extract_thumbnail(artifact_path)

        job.artifact_path = artifact_path
        final_percent, final_label = complete_stage("complete")
        job.progress_percent = final_percent
        job.current_step = final_label
        job.status = JobStatus.COMPLETED.value
        job.completed_at = datetime.utcnow()

        # The single point where a credit is spent. It sits here, past every gate above,
        # because the user is charged for a delivered artifact and nothing else -- a
        # render that crashed, failed validation or vanished never reaches this line and
        # so never costs anything.
        #
        # Staged in the same transaction as the COMPLETED status below, so the two cannot
        # diverge: no job is delivered unpaid, and no credit is taken for a job the user
        # never receives.
        credit_service.consume_for_completed_job(db, job.user_id, job.id)

        # 100% and COMPLETED land in one transaction: a client polling between two commits
        # must never see a finished job still showing 97%, or a full bar on a running job.
        db.commit()

        logger.info(
            f"JOB COMPLETED: mp4={artifact_path} size={final_size} "
            f"at {datetime.utcnow().isoformat()}Z"
        )
        logger.info(f"Workflow completed successfully for Job {job.id} in {(time.time() - start_time):.2f}s!")

    except Exception as e:
        logger.error(f"Workflow execution failed for Job {job_id}: {e}", exc_info=True)
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = JobStatus.FAILED.value
                job.current_step = f"Failed: {str(e)}"
                
                # Log Failure Step
                fail_log = AgentExecutionLog(
                    job_id=job.id,
                    agent_name=job.agent_type if job else "unknown",
                    step_name="workflow_error",
                    input_text=str(e),
                    output_text="FAILED",
                    execution_time_ms=(time.time() - start_time) * 1000.0,
                    status="FAILED"
                )
                db.add(fail_log)
                db.commit()
        except Exception as dbe:
            logger.error(f"Error recording failure state in DB: {dbe}")
    finally:
        db.close()
