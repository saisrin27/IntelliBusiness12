import datetime
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
import fitz  # PyMuPDF
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .summarization_service import SummarizationService


class BusinessAnalyticsService:
    """Service to parse, analyze, visualize, and report on business data (CSV, Excel, PDF)."""

    def __init__(self):
        self.summarizer = SummarizationService()

    def parse_and_analyze_data(self, file_path: str, original_filename: str) -> Dict[str, Any]:
        """Parses CSV, Excel, or PDF files, computes exact mathematical metrics, and extracts AI insights."""
        path = Path(file_path)
        ext = path.suffix.lower()

        raw_df = None
        extracted_text = ""

        if ext == ".csv":
            try:
                raw_df = pd.read_csv(file_path)
            except Exception:
                raw_df = pd.read_csv(file_path, encoding="latin1")
        elif ext in [".xlsx", ".xls"]:
            raw_df = pd.read_excel(file_path)
        elif ext == ".pdf":
            # PDF text extraction
            doc = fitz.open(file_path)
            pages_text = []
            for page in doc:
                pages_text.append(page.get_text())
            extracted_text = "\n".join(pages_text)

        key_stats = {}
        charts_config = []
        insights = []

        if raw_df is not None and not raw_df.empty:
            # Clean dataframe column names
            raw_df.columns = [str(c).strip() for c in raw_df.columns]

            total_rows = len(raw_df)
            key_stats["Total Records / Rows"] = total_rows

            # Detect numerical and categorical columns
            numeric_cols = raw_df.select_dtypes(include=["number"]).columns.tolist()
            text_cols = raw_df.select_dtypes(include=["object", "category"]).columns.tolist()

            # Find potential revenue / sales / amount column
            revenue_col = None
            for col in numeric_cols:
                c_lower = col.lower()
                if any(k in c_lower for k in ["revenue", "sales", "total", "amount", "price", "subtotal", "cost"]):
                    revenue_col = col
                    break
            if not revenue_col and numeric_cols:
                revenue_col = numeric_cols[0]

            if revenue_col:
                tot_val = float(raw_df[revenue_col].sum())
                avg_val = float(raw_df[revenue_col].mean())
                max_val = float(raw_df[revenue_col].max())
                min_val = float(raw_df[revenue_col].min())

                key_stats["Total Amount / Revenue"] = f"₹{tot_val:,.2f}" if "₹" not in str(tot_val) else f"{tot_val:,.2f}"
                key_stats["Average Transaction Value"] = f"₹{avg_val:,.2f}"
                key_stats["Maximum Transaction Value"] = f"₹{max_val:,.2f}"

            # Find date / time column
            date_col = None
            for col in raw_df.columns:
                c_lower = col.lower()
                if any(k in c_lower for k in ["date", "time", "month", "created", "day"]):
                    date_col = col
                    break

            # Find category / product column
            category_col = None
            for col in text_cols:
                c_lower = col.lower()
                if any(k in c_lower for k in ["product", "category", "item", "name", "type", "region", "customer", "vendor"]):
                    category_col = col
                    break

            if category_col and revenue_col:
                top_cat = raw_df.groupby(category_col)[revenue_col].sum().sort_values(ascending=False)
                if not top_cat.empty:
                    best_item = top_cat.index[0]
                    key_stats[f"Top Performing {category_col}"] = str(best_item)

                    # Build Bar Chart config for top items
                    top_5 = top_cat.head(6)
                    charts_config.append({
                        "id": "chart_category_bar",
                        "title": f"Total {revenue_col} by {category_col}",
                        "type": "bar",
                        "labels": [str(x) for x in top_5.index],
                        "data": [round(float(v), 2) for v in top_5.values],
                    })

            if date_col and revenue_col:
                try:
                    raw_df["_parsed_date"] = pd.to_datetime(raw_df[date_col], errors="coerce")
                    date_grouped = raw_df.dropna(subset=["_parsed_date"]).groupby(raw_df["_parsed_date"].dt.strftime("%Y-%m-%d"))[revenue_col].sum()
                    if not date_grouped.empty:
                        charts_config.append({
                            "id": "chart_time_line",
                            "title": f"{revenue_col} Over Time",
                            "type": "line",
                            "labels": [str(x) for x in date_grouped.index],
                            "data": [round(float(v), 2) for v in date_grouped.values],
                        })
                except Exception:
                    pass

            # Summary table snippet for AI
            summary_table = raw_df.head(10).to_string()
            data_context = (
                f"File: {original_filename}\n"
                f"Total Rows: {total_rows}\n"
                f"Columns: {', '.join(raw_df.columns)}\n"
                f"Calculated Metrics: {json.dumps(key_stats)}\n\n"
                f"Sample Table Data:\n{summary_table}"
            )

        else:
            # Extract PDF statistics using Regex & NLP
            invoice_totals = re.findall(r"(?:total|amount|due|subtotal|balance)[\s:]*[₹\$]?\s*([\d,]+\.?\d*)", extracted_text, re.IGNORECASE)
            dates = re.findall(r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})\b", extracted_text)

            key_stats["Document Type"] = "PDF Business Document / Invoice"
            key_stats["Extracted Text Characters"] = len(extracted_text)

            if invoice_totals:
                cleaned_amounts = []
                for val in invoice_totals:
                    try:
                        cleaned_amounts.append(float(val.replace(",", "")))
                    except Exception:
                        pass
                if cleaned_amounts:
                    key_stats["Detected Amount / Total"] = f"₹{max(cleaned_amounts):,.2f}"

            if dates:
                key_stats["Detected Date"] = dates[0]

            data_context = (
                f"File: {original_filename}\n"
                f"Extracted Statistics: {json.dumps(key_stats)}\n\n"
                f"Extracted Document Text:\n{extracted_text[:2500]}"
            )

        # Call Gemini AI to extract key insights grounded strictly in calculated metrics
        prompt = (
            "You are IntelliBusiness Executive Analyst.\n"
            "Analyze the following real business data and provide 4 to 5 crisp, professional bullet points highlighting key insights, revenue trends, top items, and notable observations.\n"
            "Do NOT invent numbers or fabricate values not supported by the data.\n\n"
            f"{data_context}\n\n"
            "Format your response strictly as a JSON array of strings: [\"insight 1\", \"insight 2\", \"insight 3\", \"insight 4\"]"
        )

        try:
            raw_ai = self.summarizer._call_gemini_api(prompt).strip()
            if "```json" in raw_ai:
                raw_ai = raw_ai.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_ai:
                raw_ai = raw_ai.split("```")[1].split("```")[0].strip()

            insights = json.loads(raw_ai)
            if not isinstance(insights, list):
                insights = [str(raw_ai)]
        except Exception:
            insights = [
                f"Analyzed {original_filename} successfully.",
                f"Identified {len(key_stats)} core key statistics.",
                "Calculations grounded strictly in real uploaded data.",
            ]

        return {
            "filename": original_filename,
            "key_stats": key_stats,
            "charts_config": charts_config,
            "insights": insights,
            "data_context": data_context,
        }

    def answer_data_question(self, dataset_info: Dict[str, Any], user_question: str) -> str:
        """Answers user natural-language questions grounded in actual uploaded dataset statistics."""
        data_context = dataset_info.get("data_context", "")
        key_stats = dataset_info.get("key_stats", {})
        filename = dataset_info.get("filename", "Uploaded File")

        prompt = (
            "You are IntelliBusiness AI Data Assistant.\n"
            "Answer the user's question using ONLY the provided actual business data below as the ground truth.\n"
            "If the question asks for a total, count, average, or specific stat, reference the calculated metrics.\n"
            "Do NOT invent fake numbers or speculate beyond the provided data context.\n\n"
            f"FILE: {filename}\n"
            f"CALCULATED METRICS: {json.dumps(key_stats)}\n\n"
            f"DATA CONTEXT:\n{data_context}\n\n"
            f"USER QUESTION: {user_question}\n\n"
            "Provide a helpful, precise answer in clear executive phrasing."
        )

        try:
            answer = self.summarizer._call_gemini_api(prompt).strip()
            return answer
        except Exception as exc:
            return f"Based on the dataset stats, here is the relevant information: {json.dumps(key_stats)}"

    def generate_pdf_report(self, dataset_info: Dict[str, Any], output_pdf_path: str) -> str:
        """Generates a executive PDF Business Analysis Report using reportlab."""
        doc = SimpleDocTemplate(
            output_pdf_path,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#1e293b"),
            spaceAfter=6,
        )
        subtitle_style = ParagraphStyle(
            "ReportSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#64748b"),
            spaceAfter=15,
        )
        section_style = ParagraphStyle(
            "SectionHeader",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#2563eb"),
            spaceBefore=12,
            spaceAfter=8,
        )
        body_style = ParagraphStyle(
            "ReportBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#334155"),
            spaceAfter=6,
        )

        story = []

        # Title & Subtitle
        story.append(Paragraph("BUSINESS ANALYSIS REPORT", title_style))
        story.append(Paragraph(f"Generated by IntelliBusiness AI Analytics &bull; Date: {datetime.date.today().strftime('%B %d, %Y')}", subtitle_style))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=15))

        # Executive Summary / File details
        story.append(Paragraph("Executive Summary", section_style))
        filename = dataset_info.get("filename", "Dataset")
        story.append(Paragraph(f"This automated analysis report presents structured business intelligence derived directly from <b>{filename}</b>.", body_style))

        # Key Statistics Table
        story.append(Paragraph("Key Business Statistics", section_style))
        key_stats = dataset_info.get("key_stats", {})
        if key_stats:
            table_data = [["Metric", "Value"]]
            for k, v in key_stats.items():
                table_data.append([str(k), str(v)])

            t = Table(table_data, colWidths=[240, 280])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ]))
            story.append(t)
            story.append(Spacer(1, 10))

        # Key Insights
        story.append(Paragraph("Key Strategic Insights", section_style))
        insights = dataset_info.get("insights", [])
        for item in insights:
            story.append(Paragraph(f"&bull; {item}", body_style))

        # Build PDF Document
        doc.build(story)
        return output_pdf_path


business_analytics_service = BusinessAnalyticsService()
