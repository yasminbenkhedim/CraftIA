# CraftAI — Activation des moteurs IA réels (ComfyUI FLUX + Wav2Lip)

> Ce document explique comment **activer les vrais moteurs de génération IA** de
> l'architecture « Master Remix ». Le code est déjà branché dans le pipeline ;
> il suffit d'installer les dépendances/modèles et de renseigner quelques
> variables dans `.env`.
>
> **Contexte matériel important**
> La machine de développement actuelle ne possède **pas de GPU NVIDIA** (seulement
> un GPU intégré Intel Iris Xe). ComfyUI + FLUX **ne peuvent pas tourner localement
> ici**. Ces instructions sont destinées au **PC du développeur d'origine équipé
> d'une RTX 4050** (ou tout GPU NVIDIA récent).
>
> Tant que les moteurs réels ne sont pas activés, le pipeline continue de
> fonctionner grâce à des **fallbacks honnêtes** (Pexels + placeholders
> procéduraux clairement étiquetés). Aucun élément procédural n'est présenté
> comme une sortie IA réelle.
>
> ---
>
> ## ⚠️ À LIRE EN PREMIER — points corrigés le 2026-07-30
>
> Plusieurs affirmations de ce document (rédigées le 2026-07-29) étaient **inexactes
> vis-à-vis du chemin de rendu réel**. Elles ont été corrigées ci-dessous, mais
> voici l'essentiel à retenir :
>
> 1. **Le rendu vidéo s'exécute dans le process `uvicorn` (backend), PAS dans le
>    worker Celery.** Il est déclenché par `BackgroundTasks` dans
>    [`backend/app/api/endpoints/jobs.py`](backend/app/api/endpoints/jobs.py) →
>    [`backend/app/orchestrator/workflow.py`](backend/app/orchestrator/workflow.py).
>    ➡️ Pour appliquer un changement, **relancer `start_backend.ps1`**, pas le worker.
>
> 2. **L'interpréteur qui rend est Python313 (celui du PATH utilisé par `uvicorn`),
>    PAS le `.venv`.** Les dépendances Wav2Lip (`librosa`, `torch`, `opencv`)
>    doivent donc être installées **dans Python313** (fait le 2026-07-30). Le `.venv`
>    ne sert qu'au worker Celery, qui ne participe pas au rendu.
>
> 3. **Wav2Lip n'est appelé que sur les scènes `presenter_mode=True`, or le
>    planificateur n'en met jamais.** Utiliser la variable `WAV2LIP_FORCE_PRESENTER=1`
>    (voir §2.5) pour forcer une scène présentateur et voir le vrai lip-sync s'exécuter.
>
> 4. **Pexels est bloqué par le réseau d'entreprise** (`api.pexels.com` →
>    `ConnectionResetError [WinError 10054]`). La clé est valide, mais sans proxy
>    joignable le provider reste en fallback (désormais clairement loggé). Renseigner
>    `PEXELS_PROXY` / `HTTPS_PROXY` dans `.env` pour l'activer.

---

## 0. Vue d'ensemble

| Moteur | Rôle | Statut du code | Ce qu'il faut pour l'activer |
|--------|------|----------------|------------------------------|
| **Pexels** | B-roll stock réel | ⚠️ Clé OK mais **bloqué réseau** | `PEXELS_API_KEY` (fait) **+ un proxy joignable** (`PEXELS_PROXY`/`HTTPS_PROXY`) car `api.pexels.com` est bloqué ici |
| **ComfyUI + FLUX** | Images IA photoréalistes locales | ✅ Branché, fallback si absent | GPU NVIDIA + ComfyUI + modèles FLUX |
| **Wav2Lip** | Présentateur parlant (lip-sync) | ✅ **ACTIF (CPU) via le backend uvicorn** | deps dans **Python313** (fait) + `WAV2LIP_FORCE_PRESENTER=1` pour déclencher (voir §2) |
| **FLORA** | Génération cloud (optionnel) | ⚠️ Nécessite clé API | `FLORA_API_KEY` |

Comportement automatique :
- Si un moteur est **disponible** → il produit une sortie réelle.
- Si un moteur est **absent/indisponible** → le pipeline bascule proprement sur
  un fallback étiqueté (`is_placeholder=True` / `is_real_lipsync=False`) sans
  jamais planter.

---

## 1. ComfyUI + FLUX (images IA locales)

### 1.1 Prérequis matériels
- GPU **NVIDIA** avec pilotes récents (RTX 4050 convient).
- ~12–16 Go d'espace disque pour les modèles FLUX.
- CUDA fonctionnel (`nvidia-smi` doit répondre).

Vérifier le GPU :
```powershell
nvidia-smi
```

### 1.2 Installer ComfyUI
```powershell
# Se placer où l'on veut installer ComfyUI (hors du repo CraftAI)
cd C:\Outils
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI

# Créer un environnement Python dédié
python -m venv venv
.\venv\Scripts\Activate.ps1

# PyTorch avec support CUDA (adapter cuXXX à votre version CUDA)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Dépendances ComfyUI
pip install -r requirements.txt
```

### 1.3 Télécharger les modèles FLUX
Placer les fichiers dans les sous-dossiers de `ComfyUI/models` :

| Fichier | Dossier ComfyUI | Source |
|---------|-----------------|--------|
| `flux1-schnell-fp8.safetensors` | `models/unet/` | Hugging Face — `black-forest-labs/FLUX.1-schnell` (variante fp8) |
| `t5xxl_fp8_e4m3fn.safetensors` | `models/clip/` | Hugging Face — encodeurs FLUX text |
| `clip_l.safetensors` | `models/clip/` | Hugging Face — encodeurs FLUX text |
| `ae.safetensors` | `models/vae/` | Hugging Face — VAE FLUX |

```powershell
# Exemple (nécessite un compte HF + huggingface-cli login si le repo est gated)
pip install "huggingface_hub[cli]"
huggingface-cli login

# Adapter les repo_id/nom exacts selon la page HF de FLUX.1-schnell
huggingface-cli download black-forest-labs/FLUX.1-schnell flux1-schnell.safetensors --local-dir .\models\unet
```
> ⚠️ Les noms de fichiers publiés sur Hugging Face évoluent. Vérifiez la page du
> modèle et **faites correspondre les noms** avec les variables `.env` ci-dessous.

### 1.4 Lancer ComfyUI en service
```powershell
cd C:\Outils\ComfyUI
.\venv\Scripts\Activate.ps1
python main.py --listen 127.0.0.1 --port 8188
```
Vérifier qu'il répond :
```powershell
curl http://127.0.0.1:8188/system_stats
```

### 1.5 Configurer CraftAI (`.env`)
Décommenter et ajuster dans `.env` à la racine du projet :
```env
COMFYUI_HOST=127.0.0.1
COMFYUI_PORT=8188
COMFYUI_UNET_NAME=flux1-schnell-fp8.safetensors
COMFYUI_CLIP_NAME1=t5xxl_fp8_e4m3fn.safetensors
COMFYUI_CLIP_NAME2=clip_l.safetensors
COMFYUI_VAE_NAME=ae.safetensors
# Optionnel :
# COMFYUI_STEPS=4
# COMFYUI_POLL_TIMEOUT=120
```
> Les `*_NAME` **doivent correspondre exactement** aux fichiers déposés dans
> `ComfyUI/models/...`.

### 1.6 Relancer le backend CraftAI
```powershell
# À la racine du projet CraftAI — le rendu (et donc l'appel à ComfyUI) tourne
# dans uvicorn, PAS dans le worker. C'est le backend qu'on relance.
.\start_backend.ps1
```
> ⚠️ `start_worker.ps1` (Celery) ne participe pas au rendu vidéo. Pour toute prise
> en compte d'un changement lié au rendu (ComfyUI, Wav2Lip, `.env`), relancer
> `start_backend.ps1`.

### 1.7 Vérification
- Générer une vidéo depuis le frontend.
- Dans `project_manifest.json`, les candidats ComfyUI doivent porter
  `is_placeholder: false`.
- Si ComfyUI est arrêté, le pipeline reprend Pexels/placeholder sans planter.

---

## 2. Wav2Lip (présentateur parlant / lip-sync réel) — ✅ ACTIF (CPU)

Le moteur est **branché ET opérationnel** sur cette machine (inférence CPU, sans
GPU NVIDIA). Après la TTS, le pipeline appelle `PresenterSceneOrchestrator` pour
chaque scène marquée `presenter_mode=True` et produit un **vrai lip-sync GAN**
(`method: "wav2lip_gan"`, `is_real_lipsync: true`). Si une dépendance manquait, il
**basculerait proprement** sur un fallback étiqueté.

> ⚠️ **Deux conditions indispensables** pour que le lip-sync réel s'exécute
> réellement pendant une génération lancée depuis le frontend :
> 1. Les dépendances doivent être dans **Python313** (l'interpréteur du backend
>    `uvicorn`), pas seulement dans le `.venv`. — Fait le 2026-07-30.
> 2. Au moins une scène doit être en `presenter_mode=True`. Le planificateur n'en
>    met jamais → utiliser **`WAV2LIP_FORCE_PRESENTER=1`** (§2.5).

> ✅ **Validé** le 2026-07-30 dans le Python du backend :
> `REAL LIPSYNC AVAILABLE: True` (checkpoint + repo Wav2Lip + `torch`/`librosa`/`cv2`
> tous résolus). Le script historique
> [`backend/test_wav2lip_real_e2e.py`](backend/test_wav2lip_real_e2e.py) reste
> une preuve E2E (image + WAV → MP4 H.264 + AAC).

### 2.1 Ce qui est DÉJÀ installé dans **Python313** (l'interpréteur du backend)
> ⚠️ Le rendu tourne dans `uvicorn` = **Python313 du PATH**
> (`C:\Users\<user>\AppData\Local\Programs\Python\Python313\python.exe`), **pas** le
> `.venv`. C'est là que ces paquets doivent être présents.

| Composant | Version / emplacement (Python313) |
|-----------|-----------------------------------|
| PyTorch (CPU) | `torch 2.8.0+cpu` |
| OpenCV | `opencv-python 4.11.0` |
| Audio | `librosa 0.11.0`, `soundfile`, `numpy`, `scipy` |
| Divers | `tqdm`, `imageio-ffmpeg` (mux audio) |
| Dépôt Wav2Lip | [`third_party/Wav2Lip`](third_party/Wav2Lip) (modules `models`, `audio`, `face_detection`) |
| Checkpoint GAN | [`storage/models/wav2lip_gan.pth`](storage/models/wav2lip_gan.pth) (~416 Mo) |
| Détecteur de visage s3fd | `third_party/Wav2Lip/face_detection/detection/sfd/s3fd.pth` (~86 Mo) |

### 2.2 Reproduire l'installation sur une autre machine

Depuis la racine du projet. **Cibler explicitement l'interpréteur du backend**
(celui que `uvicorn` utilise), pas le `.venv` :
```powershell
# Remplacer PYBACK par le python du backend (celui du PATH lancé par start_backend.ps1)
$PYBACK = "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python313\python.exe"

# 1) Dépendances Python (CPU ; pour GPU voir la note plus bas)
& $PYBACK -m pip install opencv-python librosa soundfile tqdm imageio-ffmpeg
& $PYBACK -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# 2) Dépôt Wav2Lip (fournit models / audio / face_detection)
git clone https://github.com/Rudrabha/Wav2Lip.git third_party\Wav2Lip

# 3) Télécharger les poids (checkpoint GAN + s3fd) via le script fourni
& $PYBACK third_party\download_checkpoints.py
```
> ℹ️ **Réseau :** `huggingface.co` est bloqué sur ce réseau (connexion réinitialisée).
> Le checkpoint GAN est donc récupéré depuis un miroir **GitHub Releases**
> (`justinjohn0306/Wav2Lip`), et s3fd depuis `adrianbulat.com`. Le script
> [`third_party/download_checkpoints.py`](third_party/download_checkpoints.py)
> essaie plusieurs miroirs et valide la taille du fichier.

> 🔧 **Compatibilité versions récentes** — trois fichiers du dépôt ont été patchés :
> - `audio.py` : `librosa.filters.mel(sr=..., n_fft=...)` (args nommés, librosa ≥ 0.10) ;
> - `inference.py` + `face_detection/.../sfd_detector.py` : `torch.load(..., weights_only=False)` (torch ≥ 2.6).

### 2.3 Configuration CraftAI (`.env`) — déjà appliquée
```env
WAV2LIP_ENABLED=1
WAV2LIP_CHECKPOINT=storage/models/wav2lip_gan.pth
WAV2LIP_REPO_DIR=third_party/Wav2Lip
WAV2LIP_DEVICE=cpu
WAV2LIP_FPS=25
WAV2LIP_IMG_SIZE=96

# Forcer une scène présentateur même si le storyboard n'en définit pas (0/1).
WAV2LIP_FORCE_PRESENTER=0
# WAV2LIP_PRESENTER_SCENE_IDS=scene_1   # optionnel : cibler des scènes précises (CSV)
```
- `WAV2LIP_REPO_DIR` : chemin du dépôt (relatif à la racine → résolu en absolu, ajouté en tête du `sys.path`).
  **Depuis le 2026-07-30, si cette variable est absente/vide, le code retombe
  automatiquement sur `third_party/Wav2Lip`** — le lip-sync réel fonctionne donc
  même si `.env` n'est pas chargé dans le process de rendu (cas du rendu in-uvicorn).
- `WAV2LIP_DEVICE` : `cpu` ici. Sur un PC à GPU NVIDIA, mettre `cuda` et installer
  la build CUDA de PyTorch (`--index-url https://download.pytorch.org/whl/cu121`).

### 2.4 Test de bout en bout
```powershell
$PYBACK = "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python313\python.exe"
& $PYBACK backend\test_wav2lip_real_e2e.py
# Attendu : method=wav2lip_gan, is_real_lipsync=True, clip MP4 (vidéo+audio)
```

### 2.5 Déclencher une scène « présentateur »

**Option A — Forçage global (recommandé pour tester).** Dans `.env` :
```env
WAV2LIP_FORCE_PRESENTER=1
# WAV2LIP_PRESENTER_SCENE_IDS=scene_1,scene_3   # optionnel ; sinon seule la 1re scène est forcée
```
Aucune modification du storyboard n'est nécessaire : le code force `presenter_mode`
au moment de la synthèse (voir
[`PresenterSceneOrchestrator._maybe_force_presenter_mode`](agents/video/wav2lip_engine.py:541)).

**Option B — Storyboard explicite.** Marquer une scène directement :
```json
{
  "scene_id": "scene_1",
  "scene_title": "Introduction",
  "presenter_mode": true,
  "presenter_avatar_image": "C:/chemin/vers/portrait.png"
}
```
- `presenter_avatar_image` : portrait/visage source à animer.
- Si absent, un cadre présentateur par défaut est utilisé.

### 2.6 Relancer **le backend** (pas le worker) et vérifier
```powershell
# Le rendu tourne dans uvicorn (BackgroundTasks), donc c'est LE BACKEND qu'on relance.
.\start_backend.ps1
```
> ⚠️ **Ne pas confondre :** `start_worker.ps1` lance le worker Celery, qui **ne fait
> pas** le rendu vidéo. Pour toute prise en compte d'un changement de code ou de
> `.env` côté rendu, relancer `start_backend.ps1`. Comme les variables d'env sont
> lues au démarrage, un changement de `WAV2LIP_FORCE_PRESENTER` **exige** un
> redémarrage (le `--reload` ne recharge que le code Python, pas le `.env`).

Dans les logs `uvicorn`, chercher :
- `[WAV2LIP] WAV2LIP_FORCE_PRESENTER active -> forced presenter_mode=True on scene(s): scene_1`
- `[WAV2LIP] processing 1 presenter scene(s); real_lipsync_available=True (real GAN lip-sync will be used)`

Dans `project_manifest.json`, le manifeste présentateur indique :
- `is_real_lipsync: true` + `method: "wav2lip_gan"` = **lip-sync réel** ;
- `is_real_lipsync: false` + `method: "procedural_animated"` = bouche animée sur
  l'enveloppe audio (non réel, étiqueté).

---

## 3. FLORA (génération cloud — optionnel)

Fournir une clé pour activer le provider cloud :
```env
FLORA_API_KEY=xxxxxxxx
```
Sans clé, le provider reste inactif (fallback), ce qui est le comportement normal.

---

## 4. Récapitulatif `.env`

```env
# Stock réel (clé OK, mais api.pexels.com est bloqué par le réseau ici)
PEXELS_API_KEY=<votre_cle>
# Proxy pour joindre api.pexels.com si le réseau d'entreprise le bloque.
# Ex: PEXELS_PROXY=http://proxy.pwc.com:8080  (HTTPS_PROXY est aussi lu)
# PEXELS_PROXY=

# ComfyUI FLUX (PC avec GPU NVIDIA)
COMFYUI_HOST=127.0.0.1
COMFYUI_PORT=8188
COMFYUI_UNET_NAME=flux1-schnell-fp8.safetensors
COMFYUI_CLIP_NAME1=t5xxl_fp8_e4m3fn.safetensors
COMFYUI_CLIP_NAME2=clip_l.safetensors
COMFYUI_VAE_NAME=ae.safetensors

# Wav2Lip présentateur parlant (ACTIF, CPU) — deps requises dans Python313 (backend)
WAV2LIP_ENABLED=1
WAV2LIP_CHECKPOINT=storage/models/wav2lip_gan.pth
WAV2LIP_REPO_DIR=third_party/Wav2Lip
WAV2LIP_DEVICE=cpu
WAV2LIP_FPS=25
WAV2LIP_IMG_SIZE=96
# Forcer une scène présentateur pour déclencher le lip-sync réel (0/1) :
WAV2LIP_FORCE_PRESENTER=0
# WAV2LIP_PRESENTER_SCENE_IDS=scene_1   # optionnel (CSV) ; sinon 1re scène uniquement

# FLORA cloud (optionnel)
# FLORA_API_KEY=<votre_cle>
```

---

## 5. Comportement de repli (robustesse)

| Situation | Comportement |
|-----------|--------------|
| ComfyUI arrêté / modèles absents | Pexels puis placeholder procédural (`is_placeholder=true`) |
| **`api.pexels.com` bloqué (réseau) et pas de proxy** | Placeholder procédural étiqueté + log `[FALLBACK]` explicite (**cas actuel**) |
| Wav2Lip absent / pas de PyTorch / pas d'OpenCV **dans Python313** | Scène présentateur rendue en b-roll normal (aucun plantage) |
| `WAV2LIP_FORCE_PRESENTER` non activé & storyboard sans présentateur | Wav2Lip **non appelé** ; log `[WAV2LIP] SKIPPED` |
| Checkpoint Wav2Lip présent mais inférence échoue | Fallback bouche animée (`is_real_lipsync=false`) |
| Aucune clé Pexels | Placeholder procédural étiqueté |

Le pipeline ne présente **jamais** une sortie de repli comme une génération IA
réelle : chaque candidat/clip porte un indicateur explicite dans le manifeste.

---

## 6. Fichiers concernés (référence)

- [`agents/video/providers/comfyui_provider.py`](agents/video/providers/comfyui_provider.py) — workflow FLUX complet + polling + download + métadonnées honnêtes.
- [`agents/video/wav2lip_engine.py`](agents/video/wav2lip_engine.py) — inférence Wav2Lip GAN réelle + fallback procédural étiqueté + `PresenterSceneOrchestrator`.
- [`agents/video/storyboard.py`](agents/video/storyboard.py) — champs `presenter_mode`, `presenter_avatar_image`, `presenter_clip_path`, `presenter_is_real_lipsync`.
- [`agents/video/pipeline.py`](agents/video/pipeline.py) — étape 3.4 : synthèse présentateur après la TTS.
- [`agents/video/python_editor/renderer.py`](agents/video/python_editor/renderer.py) — consommation des clips présentateur en arrière-plan.
- [`.env`](.env) — variables d'activation.
