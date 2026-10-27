# Sample data pack (100% fictional)

Every person, email, phone number and company here is invented (company: "Nimbus Technologies").
Use this instead of real employee resumes while building and testing.

## Contents
| Path | What it is | Used in |
|---|---|---|
| `employees.csv` | The "HR export": 16 employees with department, location, availability | Step 4 (CSV import) |
| `resumes/` | 15 resumes in 4 formats (one employee, EMP-1016, deliberately has none) | Steps 4-6 (upload, parse, chunk, embed) |
| `roles.json` | 3 project roles + the ranking a human expert would expect, with reasons | Steps 7-8 (matching), Step 14 (evaluation) |

## Resumes
| Code | Name | Role | Format | Availability | File |
|---|---|---|---|---|---|
| EMP-1001 | Ananya Iyer | Senior Backend Engineer | PDF (text) | available (0%) | `EMP-1001_ananya_iyer.pdf` |
| EMP-1002 | Rohan Mehta | Backend Engineer | Word .docx (skills in a table) | partial (50%) | `EMP-1002_rohan_mehta.docx` |
| EMP-1003 | Priya Nair | DevOps Engineer | PDF (two-column) | available (0%) | `EMP-1003_priya_nair.pdf` |
| EMP-1004 | Arjun Reddy | Full-Stack Engineer | PDF (text) | allocated (100%) | `EMP-1004_arjun_reddy.pdf` |
| EMP-1005 | Sneha Kulkarni | Frontend Engineer | Word .docx (skills in a table) | available (0%) | `EMP-1005_sneha_kulkarni.docx` |
| EMP-1006 | Vikram Singh | Principal Engineer – Java | PDF (text) | partial (50%) | `EMP-1006_vikram_singh.pdf` |
| EMP-1007 | Kavya Menon | Data Scientist – NLP | PDF (text) | available (0%) | `EMP-1007_kavya_menon.pdf` |
| EMP-1008 | Aditya Joshi | Data Engineer | PDF (scanned image, no text) | allocated (100%) | `EMP-1008_aditya_joshi_scanned.pdf` |
| EMP-1009 | Meera Pillai | QA Automation Engineer | Word .docx (skills in a table) | available (0%) | `EMP-1009_meera_pillai.docx` |
| EMP-1010 | Karthik Rao | Software Engineer (Python) | PDF (text) | available (0%) | `EMP-1010_karthik_rao.pdf` |
| EMP-1011 | Neha Gupta | Frontend Lead – Angular | PDF (text) | available (0%) | `EMP-1011_neha_gupta.pdf` |
| EMP-1012 | Siddharth Bose | Cloud Architect – Azure | Word .docx (skills in a table) | partial (70%) | `EMP-1012_siddharth_bose.docx` |
| EMP-1013 | Fatima Shaikh | ML Engineer – MLOps | PDF (text) | partial (50%) | `EMP-1013_fatima_shaikh.pdf` |
| EMP-1014 | Rahul Verma | Backend Engineer – Go | PDF (text) | available (0%) | `EMP-1014_rahul_verma.pdf` |
| EMP-1015 | Divya Krishnan | Engineering Manager | Word .docx (skills in a table) | available (0%) | `EMP-1015_divya_krishnan.docx` |

## Edge cases built in on purpose
- **Two-column PDF** (EMP-1003): naive text extraction can mix sidebar and main column.
- **Scanned PDF** (EMP-1008): an image only, no text layer, so it needs OCR (we detect this in Step 4).
- **DOCX with a skills table** (all .docx files): table text is missed by simple paragraph-only extraction.
- **Abbreviations**: "k8s" (EMP-1003, EMP-1014), "JS" / "Angular 2+" (EMP-1011) -> skill normalisation (Step 5).
- **Experience maths**: EMP-1002 has 6 years total but only 4 in Python; EMP-1015's Django is from before 2019.
- **Varied date formats**: "Jun 2021 – Present", "03/2022 - Present", "2018 – 2020".
- **Availability**: fully allocated stars (EMP-1004, EMP-1008) should rank below available good matches.
- **Employee without a resume**: EMP-1016 is in the CSV only.
