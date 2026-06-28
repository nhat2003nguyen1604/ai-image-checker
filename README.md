# AI Image Checker

AI Image Checker is a full-stack web application that analyzes uploaded images and provides an explainable AI-generated image detection result. The app combines image forensic signals, metadata analysis, heuristic scoring, and an optional hybrid machine learning detector.

## Features

- Image upload with preview
- Drag-and-drop upload support
- Explainable scan results with label, confidence score, and reasons
- Detection quality badge: Weak, Mixed, or Strong evidence
- Technical signals view for transparency
- Shareable scan report pages
- User feedback system: Correct / Wrong with optional notes
- Admin dashboard for reviewing feedback
- Admin feedback workflow: New / Reviewed / Fixed
- Auto-refreshing admin feedback review
- Light and dark mode UI
- Support chatbot for basic app guidance

## Tech Stack

### Frontend
- Next.js
- TypeScript
- Tailwind CSS

### Backend
- FastAPI
- Python
- Pillow
- NumPy
- Optional Hugging Face / Transformers model detector

### Storage
- Local JSONL file storage for scan reports and feedback

## Project Structure

```txt
ai-image-checker/
  backend/
    main.py
    storage.py
    detector.py
    forensics.py
    model_detector.py
    chatbot.py
    requirements.txt

  frontend/
    app/
      page.tsx
      admin/
      report/[scan_id]/
    package.json
    tailwind.config.js

  README.md
  LICENSE
