import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Job, JobCreate } from '../models/job.model';
import { AuthService } from './auth.service';

/**
 * Job API client.
 *
 * Authorization headers are attached centrally by authInterceptor — this service
 * deliberately does NOT set them. The previous manual header also fell back to a
 * literal 'demo-token', which made an expired session look like a working one
 * until the backend rejected it.
 */
@Injectable({
  providedIn: 'root'
})
export class JobService {
  private apiUrl = 'http://localhost:8000/api';

  constructor(private http: HttpClient, private auth: AuthService) {}

  createJob(jobData: JobCreate): Observable<Job> {
    return this.http.post<Job>(`${this.apiUrl}/jobs`, jobData);
  }

  /**
   * Uploads user media for a job. Must complete BEFORE startJob(), otherwise the
   * pipeline runs without the files — which is why the job is created with
   * defer_start=true whenever there are uploads.
   */
  uploadJobMedia(jobId: string, files: File[]): Observable<any> {
    const formData = new FormData();
    files.forEach(f => formData.append('files', f, f.name));
    // No Content-Type header: the browser must set the multipart boundary itself.
    return this.http.post<any>(`${this.apiUrl}/jobs/${jobId}/uploads`, formData);
  }

  /** Starts a job that was created with defer_start=true. */
  startJob(jobId: string): Observable<Job> {
    return this.http.post<Job>(`${this.apiUrl}/jobs/${jobId}/start`, {});
  }

  listJobUploads(jobId: string): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/jobs/${jobId}/uploads`);
  }

  getJob(jobId: string): Observable<Job> {
    return this.http.get<Job>(`${this.apiUrl}/jobs/${jobId}`);
  }

  listJobs(): Observable<Job[]> {
    return this.http.get<Job[]>(`${this.apiUrl}/jobs`);
  }

  /**
   * Direct browser URL (used as <video>/<img> src and for downloads), so the token
   * travels as a query param — an interceptor can't reach those requests.
   */
  getArtifactUrl(jobId: string): string {
    const token = this.auth.token ?? '';
    return `${this.apiUrl}/artifacts/${jobId}?token=${encodeURIComponent(token)}`;
  }

  downloadArtifact(jobId: string): Observable<Blob> {
    return this.http.get(`${this.apiUrl}/artifacts/${jobId}`, { responseType: 'blob' });
  }

  /**
   * Authenticated <img> src for a job's poster frame, built from the relative
   * `thumbnail_url` the API returns. Same query-param token as getArtifactUrl, since an
   * interceptor cannot attach headers to an image request.
   */
  getThumbnailUrl(thumbnailPath: string): string {
    const token = this.auth.token ?? '';
    // The API returns '/api/jobs/{id}/thumbnail'; apiUrl already ends in '/api'.
    const path = thumbnailPath.replace(/^\/api/, '');
    return `${this.apiUrl}${path}?token=${encodeURIComponent(token)}`;
  }

  getAdvisoryTemplates(): Observable<any[]> {
    return this.http.get<any[]>(`${this.apiUrl}/v1/advisory/templates`);
  }

  analyzeAdvisory(templateId: string, inputs: any): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/v1/advisory/analyze`, {
      template_id: templateId,
      inputs: inputs
    });
  }

  getDashboardJobs(): Observable<any[]> {
    return this.http.get<any[]>(`${this.apiUrl}/v1/dashboard/jobs`);
  }

  getJobPreview(jobId: string): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/v1/dashboard/previews/${jobId}`);
  }

  getDashboardAnalytics(): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/v1/dashboard/analytics`);
  }

  getVideoPreview(jobId: string): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/v1/dashboard/video_preview/${jobId}`);
  }
}
