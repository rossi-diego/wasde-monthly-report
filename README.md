# WASDE Report Viewer

This project aims to simplify and automate the download and exploration of WASDE reports published monthly by the USDA (United States Department of Agriculture). The XML files are automatically fetched from the official source and transformed into a clean, structured dataset.

## 🔍 Features
- Automated download of WASDE XML and XLS files
- Structured extraction of supply and demand data by commodity
- Automatic classification of crop stage (Outlook, Current, Next)
- Consolidated CSV file generation for analysis
- Power BI file included for interactive visualization

## 📊 Power BI
A `.pbix` file is available in the project root. To use it:
1. Open the file using Power BI Desktop
2. Update the data source path to point to `data/raw_data/wasde_commodities_timeseries.csv` on your local machine

## 🚀 How to Use

1. Clone this repository:
```bash
git clone https://github.com/your-user/your-repo.git
cd your-repo
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Add your USDA API token to a `.env` file:
```env
WASDE_JWT=your_token_here
```
To generate your token, visit:  
👉 https://usda.library.cornell.edu/apidoc/index.html#/account/getUserToken  
Sign in or register, and then copy the token shown in the **"Authorize"** section.

5. Run the notebook or scripts inside the `notebooks/` folder.

---

### 📁 Project Structure

```
├── data/
│   ├── wasde_files/
│   ├── raw_data/
├── notebooks/
├── src/
│   ├── config.py
│   └── wasde_downloader.py
├── wasde.pbix
├── .env
├── requirements.txt
├── README.md
```
