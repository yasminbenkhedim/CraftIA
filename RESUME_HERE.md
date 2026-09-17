# État du projet

## GPU : ✅ terminé

Driver **610.88** (CUDA 13.3), `torch 2.13.0+cu126`, GTX 1650 Ti Max-Q 4 Go.
XTTS tourne sur CUDA, vérifié sur un rendu complet.

| | synthèse | facteur temps réel |
|---|---|---|
| CPU | 54,9 s | 3,61× |
| CUDA | 12,7 s | **0,82×** |

→ **4,3× plus rapide**, et plus rapide que le temps réel.

> Le tout **premier** appel CUDA après l'installation de torch paie la compilation JIT
> des kernels sm_75 (~76 s au lieu de 13 s). C'est mis en cache sur disque une fois
> pour toutes — ne pas confondre avec une régression de perf.

`XTTS_DEVICE` est auto-détecté. Mettre `XTTS_DEVICE=cpu` dans `.env` uniquement pour
laisser les 4 Go de VRAM à Wav2Lip.

## À traiter

- `CandidateFeatureExtractor` ouvre les `.mp4` avec PIL → `cannot identify image file`
  sur **chaque** clip vidéo Pexels. Les candidats vidéo sont donc notés sans features.
  (`CandidatePreValidator` avait été corrigé pour la vidéo, pas celui-ci.)

## Historique

**Corrigé récemment**
- **Cause du texte générique** : Groq avait retiré `llama-3.3-70b-versatile` → toutes les
  requêtes LLM en 404, repli silencieux sur le template. Modèle remplacé par
  `openai/gpt-oss-120b` dans `.env`. Narration désormais écrite par le LLM.
- **XTTS v2 intégré** (`agents/video/xtts_tts.py`), chaîne `xtts → piper → edge`.
  `pip install TTS` est impossible sur Python 3.13 (paquet archivé) → fork `coqui-tts` 0.27.5,
  avec `transformers` épinglé en 4.x (la 5.x casse coqui-tts).
- **Auth complète** : `/login`, `/register`, guard, intercepteur 401, logout.
- **UI premium** : shell (sidebar + header), page `/create` refondue.

**Config `.env` actuelle**
```
OPENAI_MODEL=openai/gpt-oss-120b     # vérifier api.groq.com/openai/v1/models si 404
TTS_ENGINE=xtts                      # basculer sur 'piper' si XTTS trop lent
XTTS_SPEAKER=Claribel Dervla         # 58 voix disponibles
```

## Pièges connus

- **CORS** : le frontend n'est autorisé que sur les ports **4200 / 55422 / 3000**
  (`backend/app/main.py`). Un autre port → « Could not sign in ».
- **`.env` n'est lu qu'au démarrage** du processus : `--reload` recharge le code, pas l'env.
- Le `.venv` du backend est cassé (créé sur une autre machine). Lancement utilisé :
  `python -m uvicorn app.main:app --reload` depuis `backend/`.

## Démarrage

```bash
cd backend && python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
cd frontend && ng serve --port 4200
```
