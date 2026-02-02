# Compliance Autofill Engine (CAfE)

Compliance Autofill Engine (CAfE) is an AI-assisted system that converts advisor meeting notes and client profiles into structured, audit-ready compliance documentation. The goal is to reduce manual post-meeting documentation time while improving consistency, completeness, and reliability of compliance records.

Built as part of the LPL Financial Hackathon.

---

## 🚀 Overview

Advisors often spend significant time after meetings writing compliance documentation that explains recommendations, risks, and disclosures. This process is repetitive, manual, and prone to missing information.

CAfE streamlines this workflow by:
- Ingesting advisor meeting notes and client profile information  
- Retrieving relevant compliance guidance  
- Generating structured draft documentation sections using an LLM  
- Flagging missing or incomplete fields  
- Allowing advisors to review and approve all outputs (human-in-the-loop)

CAfE is designed to assist advisors, not replace them.

---

## 🧱 Architecture

- Frontend: Web-based UI (React + Vite)
- Backend: FastAPI (Python)
- LLM Integration: AWS Bedrock
- Retrieval: Local document index (JSON chunks)
- Data Flow:
  1. User uploads PDFs or text
  2. Backend extracts text
  3. Relevant guidance is retrieved
  4. LLM generates structured JSON
  5. Backend validates/repairs JSON
  6. Frontend displays editable results

---

## 🔐 Security & Trust

- Human-in-the-loop by design  
- No automatic submissions  
- Documents processed in-memory only  
- No long-term storage of raw client files  
- Encrypted data in transit and at rest using AWS-managed services  

---

## 🧰 Tech Stack

- Python
- FastAPI
- AWS Bedrock
- React
- Vite
- JavaScript / TypeScript
- PDF parsing libraries

---

## 📁 Project Structure
compliance-autofill-engine/

├── backend/

│   ├── main.py

│   ├── bedrock_client.py

│   ├── docs_text/

│   ├── requirements.txt

│   └── data/

├── frontend/

│   ├── src/

│   └── package.json

└── README.md

---

## ▶️ Running Locally

### Backend

cd backend

python -m venv venv

source venv/bin/activate   # Mac/Linux

### Frontend

cd frontend

npm install

npm run dev

---

## 📌 Example Use Case

1. Upload a client profile PDF  
2. Upload meeting notes PDF  
3. Click “Autofill”  
4. Review generated compliance sections  
5. Edit / accept / reject each section  

---

## 👥 Team

- Eliot Boda  
- Rafael Lopez  
- Jordan Valerio  
- Jamison Kerr  
- Kalkidan Gebrekirstos  

---

## 📜 Disclaimer

This project is a hackathon prototype intended for demonstration purposes. It is not production-hardened and should not be used for real client data without further security, testing, and compliance review.

---

## ⭐ Acknowledgments

Built for the LPL Financial Hackathon.

[Demo](https://drive.google.com/file/d/1-d4ExcsMA5SceUpP7BWXqPmcS1E1uyTq/view?resourcekey)
