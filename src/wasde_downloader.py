import os
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urlparse
from config import WASDE_FOLDER, RAW_DATA


def classify_crop_stage(marketing_year: str, report_date: str) -> str:
    """Classify the marketing year stage as Outlook, Next, or Current."""
    try:
        if not isinstance(marketing_year, str):
            return "out of scope"

        marketing_year = marketing_year.strip().lower()

        if marketing_year == "outlook" or "proj." in marketing_year:
            return "Outlook year"
        elif "est." in marketing_year:
            return "Next year"
        elif re.match(r"\d{4}/\d{2}$", marketing_year):
            return "Current year"
        else:
            return "out of scope"
    except Exception:
        return "out of scope"


def fetch_wasde_releases(token, start_date="2000-01-01", end_date="2026-01-01"):
    """Fetch WASDE release metadata from USDA API."""
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }
    url = (
        f"https://usda.library.cornell.edu/api/v1/release/findByIdentifier/wasde"
        f"?latest=false&start_date={start_date}&end_date={end_date}"
    )
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()


def download_release_files(releases, limit=None):
    """Download and save WASDE XML/XLS files locally."""
    WASDE_FOLDER.mkdir(parents=True, exist_ok=True)
    downloaded = 0

    for release in releases:
        release_date = release.get("release_datetime", "")[:10]
        for file_url in release.get("files", []):
            if not file_url.endswith((".xml", ".xls")):
                continue

            filename = f"{release_date}_{os.path.basename(urlparse(file_url).path)}"
            save_path = WASDE_FOLDER / filename

            if save_path.exists():
                continue

            resp = requests.get(file_url)
            if resp.status_code == 200:
                with open(save_path, "wb") as f:
                    f.write(resp.content)
                print(f"Downloaded: {filename}")
                downloaded += 1
                if limit and downloaded >= limit:
                    return
            else:
                print(f"Failed to download {file_url}")


def extract_soybean_outlook_structured(xml_path):
    """Extract 'Outlook year' values for soybeans from specific XML structures."""
    with open(xml_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "lxml-xml")

    report_date = Path(xml_path).stem[:10]
    attribute_map = {
        "Beginning Stocks": "Beginning Stocks",
        "Production": "Production",
        "Imports": "Imports",
        "Domestic Crush": "Domestic Crush",
        "Domestic Total": "Domestic Total 2",
        "Exports": "Exports",
        "Ending Stocks": "Ending Stocks"
    }

    records = []

    for report in soup.find_all("Report"):
        if "soybean" not in report.get("sub_report_title", "").lower():
            continue

        for region_group in report.find_all(re.compile(r"m\d+_region_group\d*")):
            country = region_group.get("region2", "").strip()
            if not country:
                continue

            for month_group in region_group.find_all(re.compile(r"m\d+_month_group\d*")):
                for attr_group in month_group.find_all(re.compile(r"m\d+_attribute_group\d*")):
                    raw_attr = attr_group.get("attribute2", "").strip()
                    clean_attr = re.sub(r"\s+", " ", raw_attr).strip()
                    col_name = attribute_map.get(clean_attr)
                    if not col_name:
                        continue

                    cell = attr_group.find("Cell")
                    if cell and cell.has_attr("cell_value2"):
                        try:
                            value = float(cell["cell_value2"].replace(",", ""))
                        except ValueError:
                            continue

                        row = {
                            "report_date": report_date,
                            "commodity": "soybean",
                            "country": country,
                            "marketing_year": "Outlook",
                            "crop_stage": "Outlook year",
                            **{col: None for col in attribute_map.values()}
                        }
                        row[col_name] = value
                        records.append(row)

    df = pd.DataFrame(records)
    if not df.empty:
        df = df.groupby([
            "report_date", "commodity", "country", "marketing_year", "crop_stage"
        ], as_index=False).first()
    return df


def extract_all_marketing_years(xml_path, commodities=None):
    """Extract time series from standard WASDE XML structure."""
    if commodities is None:
        commodities = ("wheat", "soybean", "soybean oil", "soybean meal", "corn")
    commodities = sorted(commodities, key=len, reverse=True)

    with open(xml_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "lxml-xml")

    report_date = Path(xml_path).stem[:10]
    rows = []

    attribute_map = {
        "BeginningStocks": "Beginning Stocks",
        "Production": "Production",
        "Imports": "Imports",
        "DomesticFeed": "Domestic Feed",
        "DomesticTotal2/": "Domestic Total 2",
        "Exports": "Exports",
        "EndingStocks": "Ending Stocks"
    }

    for report in soup.find_all("Report"):
        title = report.get("sub_report_title", "").lower()
        matched = next((c for c in commodities if c in title or "outlook" in title), None)
        if not matched:
            continue

        for i in range(1, 7):
            matrix = report.find(f"matrix{i}")
            if not matrix:
                continue

            marketing_year = matrix.get(f"region_header{i}", "").strip()
            if not marketing_year:
                continue

            region_tag = f"region{i}"
            attribute_tag = f"attribute{i}"
            cell_value_tag = f"cell_value{i}"

            for region_group in matrix.find_all(attrs={region_tag: True}):
                country = region_group.get(region_tag, "").strip()
                row = {
                    "report_date": report_date,
                    "commodity": matched,
                    "country": country,
                    "marketing_year": marketing_year,
                    "crop_stage": classify_crop_stage(marketing_year, report_date)
                }

                for attr_group in region_group.find_all(attrs={attribute_tag: True}):
                    attr = attr_group.get(attribute_tag, "").replace(" ", "").replace("\n", "").replace("\r", "")
                    col_name = attribute_map.get(attr)
                    if col_name:
                        cell = attr_group.find("Cell")
                        if cell and cell.has_attr(cell_value_tag):
                            try:
                                row[col_name] = float(cell[cell_value_tag].replace(",", ""))
                            except ValueError:
                                row[col_name] = None

                if any(k in row for k in attribute_map.values()):
                    rows.append(row)

    return pd.DataFrame(rows)


def process_all_wasde_files():
    """Process all XML files, merging and saving as CSV."""
    xml_files = sorted(WASDE_FOLDER.glob("*.xml"))
    print(f"{len(xml_files)} XML files found in {WASDE_FOLDER}")

    latest_by_date = {Path(f).stem[:10]: f for f in xml_files}
    print(f"{len(latest_by_date)} unique report dates found.")

    all_data = []
    for date, xml_file in latest_by_date.items():
        print(f"Processing {xml_file.name}...")
        try:
            df_main = extract_all_marketing_years(xml_file)
            df_soy = extract_soybean_outlook_structured(xml_file)
            df_combined = pd.concat([df_main, df_soy], ignore_index=True) if not df_soy.empty else df_main
            print(f" → {len(df_combined)} rows extracted.")
            if not df_combined.empty:
                all_data.append(df_combined)
        except Exception as e:
            print(f"Error processing {xml_file.name}: {e}")

    if all_data:
        final_df = pd.concat(all_data, ignore_index=True)
        RAW_DATA.mkdir(parents=True, exist_ok=True)
        output_path = RAW_DATA / "wasde_commodities_timeseries.csv"
        final_df.to_csv(output_path, index=False)
        print(f"CSV saved to: {output_path}")
        return final_df

    print("No data extracted from XML files.")
    return pd.DataFrame()
