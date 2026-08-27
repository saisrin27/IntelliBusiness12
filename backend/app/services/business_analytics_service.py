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
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib.colors import HexColor

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
        """Answer calculations from the uploaded DataFrame, never from generated insights."""
        file_path = dataset_info.get("file_path")
        filename = dataset_info.get("filename", "Uploaded File")
        if not file_path:
            return "The uploaded dataset is no longer available. Please upload it again."

        try:
            dataframe = self._load_tabular_dataframe(file_path)
            if dataframe is None or dataframe.empty:
                return "This dataset does not contain tabular rows that can be calculated."
            return self._calculate_data_question(dataframe, user_question, filename)
        except ValueError as exc:
            return str(exc)
        except Exception as exc:
            print(f"[BusinessAnalyticsService] Dataset question failed: {exc}")
            return "I could not calculate that from the uploaded dataset. Please check the column names and values."

    @staticmethod
    def _load_tabular_dataframe(file_path: str) -> Optional[pd.DataFrame]:
        """Load only the stored CSV/Excel dataset; PDFs are not tabular calculation sources."""
        path = Path(file_path)
        if path.suffix.lower() == ".csv":
            try:
                dataframe = pd.read_csv(path)
            except UnicodeDecodeError:
                dataframe = pd.read_csv(path, encoding="latin1")
        elif path.suffix.lower() in {".xlsx", ".xls"}:
            dataframe = pd.read_excel(path)
        else:
            return None
        dataframe.columns = [str(column).strip() for column in dataframe.columns]
        return dataframe

    def _calculate_data_question(self, dataframe: pd.DataFrame, question: str, filename: str) -> str:
        """Interpret common business questions and execute them against Pandas values."""
        normalized_question = question.lower().strip()
        numeric_columns = []
        numeric_values = {}
        for column in dataframe.columns:
            values = pd.to_numeric(dataframe[column], errors="coerce")
            if values.notna().sum() > 0:
                numeric_columns.append(column)
                numeric_values[column] = values

        filters = self._find_filters(dataframe, normalized_question)
        requested_filter_terms = self._requested_filter_terms(normalized_question)
        missing_filter_terms = [term for term in requested_filter_terms if term not in {value.casefold() for value in filters.values()}]
        if missing_filter_terms:
            categorical_columns = ", ".join(str(column) for column in dataframe.select_dtypes(include=["object", "category"]).columns)
            return f"I could not find {', '.join(missing_filter_terms)} in the dataset. Available categorical columns: {categorical_columns or 'none'}."
        filtered = dataframe.loc[:, :].copy()
        for column, value in filters.items():
            filtered = filtered[filtered[column].astype(str).str.casefold() == value.casefold()]

        if filtered.empty:
            conditions = ", ".join(f"{column} = {value}" for column, value in filters.items())
            return f"No rows matched {conditions or 'that question'} in {filename}."

        operation = self._find_operation(normalized_question)
        target_column = self._find_numeric_column(dataframe, normalized_question, numeric_columns)
        if operation == "count":
            comparison = self._comparison_values(dataframe, normalized_question)
            if comparison:
                return " ".join(
                    f"{value}: {len(dataframe[dataframe[column].astype(str).str.casefold() == value.casefold()]):,} rows."
                    for column, value in comparison
                )
            return f"The matching row count was {len(filtered):,}."

        if operation == "percentage":
            if target_column is None:
                return "I could not identify the numeric column needed for that percentage."
            values = pd.to_numeric(filtered[target_column], errors="coerce").dropna()
            total = pd.to_numeric(dataframe[target_column], errors="coerce").sum()
            if total == 0:
                return f"The total of {target_column} is zero, so a percentage cannot be calculated."
            percentage = values.sum() / total * 100
            return f"The matching rows represented {percentage:,.2f}% of total {target_column} ({values.sum():,.2f} / {total:,.2f})."

        if target_column is None and operation != "count":
            if "revenue" in normalized_question or "sales" in normalized_question:
                target_column = self._find_numeric_column(dataframe, "amount total revenue sales", numeric_columns)
            if target_column is None and "revenue" in normalized_question:
                quantity_column = self._find_numeric_column(dataframe, "quantity qty units", numeric_columns)
                price_column = self._find_numeric_column(dataframe, "unit price", numeric_columns)
                if quantity_column and price_column:
                    filtered_values = pd.to_numeric(filtered[quantity_column], errors="coerce") * pd.to_numeric(filtered[price_column], errors="coerce")
                    values = filtered_values.dropna()
                    if operation == "sum":
                        return f"The total calculated revenue was {values.sum():,.2f} across {len(values):,} matching rows."
                    return f"The average calculated revenue was {values.mean():,.2f} across {len(values):,} matching rows."
            if target_column is None:
                return f"I could not identify a numeric column for that calculation. Available numeric columns: {', '.join(numeric_columns)}."

        group_column = self._find_group_column(dataframe, normalized_question)
        if group_column and target_column:
            grouped_answers = []
            for value, group in dataframe.groupby(group_column, dropna=True):
                group_values = pd.to_numeric(group[target_column], errors="coerce").dropna()
                if not group_values.empty:
                    grouped_answers.append(f"{value}: {self._format_calculation(operation, group_values)}")
            if grouped_answers:
                return f"{target_column} by {group_column}: " + "; ".join(grouped_answers) + "."

        comparison = self._comparison_values(dataframe, normalized_question)
        if comparison and target_column:
            comparison_answers = []
            for column, value in comparison:
                group = pd.to_numeric(
                    dataframe.loc[dataframe[column].astype(str).str.casefold() == value.casefold(), target_column],
                    errors="coerce",
                ).dropna()
                if group.empty:
                    continue
                result = self._format_calculation(operation, group)
                comparison_answers.append(f"{value}: {result} {target_column}.")
            if comparison_answers:
                return " ".join(comparison_answers)

        values = pd.to_numeric(filtered[target_column], errors="coerce").dropna()
        if values.empty:
            return f"The column {target_column} has no valid numeric values for the matching rows."

        if operation == "sum":
            return f"The total {target_column} was {values.sum():,.2f} across {len(values):,} matching rows."
        if operation == "min":
            return f"The minimum {target_column} was {values.min():,.2f}."
        if operation == "max":
            return f"The maximum {target_column} was {values.max():,.2f}."
        if operation == "median":
            return f"The median {target_column} was {values.median():,.2f}."
        if operation == "top":
            return f"The highest {target_column} was {values.max():,.2f}."
        if operation == "bottom":
            return f"The lowest {target_column} was {values.min():,.2f}."
        return f"The average {target_column} was {values.mean():,.2f} across {len(values):,} matching rows."

    @staticmethod
    def _format_calculation(operation: str, values: pd.Series) -> str:
        if operation == "sum":
            return f"{values.sum():,.2f}"
        if operation == "min" or operation == "bottom":
            return f"{values.min():,.2f}"
        if operation == "max" or operation == "top":
            return f"{values.max():,.2f}"
        if operation == "median":
            return f"{values.median():,.2f}"
        return f"{values.mean():,.2f}"

    @staticmethod
    def _find_operation(question: str) -> str:
        if any(word in question for word in ("percentage", "percent", "%", "share")):
            return "percentage"
        if any(word in question for word in ("median", "middle value")):
            return "median"
        if any(word in question for word in ("minimum", "min", "lowest", "smallest")):
            return "min"
        if any(word in question for word in ("maximum", "max", "highest", "largest")):
            return "max"
        if any(word in question for word in ("count", "number of", "how many")):
            return "count"
        if any(word in question for word in ("sum", "total", "combined")):
            return "sum"
        if any(word in question for word in ("top", "best")):
            return "top"
        if any(word in question for word in ("bottom", "worst")):
            return "bottom"
        return "mean"

    @staticmethod
    def _find_numeric_column(dataframe: pd.DataFrame, question: str, numeric_columns: List[str]) -> Optional[str]:
        question_tokens = set(re.findall(r"[a-z0-9]+", question))
        ranked = []
        for column in numeric_columns:
            column_tokens = set(re.findall(r"[a-z0-9]+", column.lower()))
            score = len(question_tokens & column_tokens)
            if any(word in question for word in ("unit price", "unitprice")) and "price" in column.lower():
                score += 10
            if any(word in question for word in ("revenue", "sales")) and any(word in column.lower() for word in ("revenue", "sales", "amount", "total")):
                score += 8
            ranked.append((score, column))
        if not ranked:
            return None
        ranked.sort(reverse=True)
        explicit_column_request = any(
            phrase in question
            for phrase in ("unit price", "price", "quantity", "qty", "revenue", "sales", "amount", "cost", "units")
        )
        return ranked[0][1] if ranked[0][0] > 0 else (None if explicit_column_request else (numeric_columns[0] if numeric_columns else None))

    @staticmethod
    def _find_filters(dataframe: pd.DataFrame, question: str) -> Dict[str, str]:
        """Find exact categorical values mentioned in the question, including follow-ups like 'What about Europe?'"""
        filters = {}
        for column in dataframe.select_dtypes(include=["object", "category"]).columns:
            values = dataframe[column].dropna().astype(str).unique().tolist()
            for value in sorted(values, key=len, reverse=True):
                if value.casefold() in question:
                    filters[column] = value
                    break
        return filters

    @staticmethod
    def _comparison_values(dataframe: pd.DataFrame, question: str) -> List[tuple[str, str]]:
        """Return multiple mentioned category values for comparison questions."""
        if not any(word in question for word in ("compare", "comparison", "versus", " vs ", " and ")):
            return []
        matches = []
        for column in dataframe.select_dtypes(include=["object", "category"]).columns:
            values = dataframe[column].dropna().astype(str).unique().tolist()
            for value in sorted(values, key=len, reverse=True):
                if value.casefold() in question:
                    matches.append((column, value))
        return matches if len(matches) > 1 else []

    @staticmethod
    def _find_group_column(dataframe: pd.DataFrame, question: str) -> Optional[str]:
        if " by " not in f" {question} ":
            return None
        categorical_columns = dataframe.select_dtypes(include=["object", "category"]).columns.tolist()
        for column in categorical_columns:
            if any(token in question for token in re.findall(r"[a-z0-9]+", column.lower())):
                return column
        return categorical_columns[0] if categorical_columns else None

    @staticmethod
    def _requested_filter_terms(question: str) -> List[str]:
        """Extract common filter values so a missing requested category is never silently ignored."""
        terms = []
        for match in re.findall(r"\b(?:in|from|for|within|between)\s+([a-z][a-z\s-]{2,40}?)(?:\?|$|\s+(?:and|with|by|what|how))", question):
            term = match.strip()
            if term and term not in terms:
                terms.append(term)
        return terms

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

        # Visualization charts from the same data used by the dashboard.
        charts_config = dataset_info.get("charts_config", [])
        chart_flowables = self._build_pdf_charts(charts_config)
        if chart_flowables:
            story.append(Paragraph("Visual Analysis", section_style))
            story.extend(chart_flowables)

        # Build PDF Document
        doc.build(story)
        return output_pdf_path

    @staticmethod
    def _build_pdf_charts(charts_config: Any) -> List[Drawing]:
        """Render stored Chart.js-compatible chart data as ReportLab drawings."""
        if not isinstance(charts_config, list):
            return []

        flowables = []
        for config in charts_config:
            if not isinstance(config, dict):
                continue
            labels = [str(label) for label in config.get("labels", [])]
            values = config.get("data", [])
            if not labels or not isinstance(values, list):
                continue
            try:
                numeric_values = [float(value) for value in values]
            except (TypeError, ValueError):
                continue

            chart_type = str(config.get("type", "bar")).lower()
            drawing = Drawing(520, 260)
            drawing.add(String(10, 242, str(config.get("title", "Chart")), fontName="Helvetica-Bold", fontSize=11, fillColor=HexColor("#1e293b")))

            if chart_type in {"pie", "doughnut"}:
                chart = Pie()
                chart.x = 150
                chart.y = 15
                chart.width = 210
                chart.height = 210
                chart.data = numeric_values
                chart.labels = labels
                chart.slices.strokeWidth = 0.5
                chart.slices.strokeColor = HexColor("#ffffff")
                chart.slices.fontName = "Helvetica"
                chart.slices.fontSize = 7
                drawing.add(chart)
            elif chart_type == "line":
                chart = LinePlot()
                chart.x = 55
                chart.y = 35
                chart.width = 440
                chart.height = 190
                chart.data = [[(index, value) for index, value in enumerate(numeric_values)]]
                chart.xValueAxis.valueMin = 0
                chart.xValueAxis.valueMax = max(len(labels) - 1, 1)
                chart.yValueAxis.valueMin = 0
                chart.yValueAxis.valueMax = max(numeric_values) * 1.1 if max(numeric_values) else 1
                chart.lines[0].strokeColor = HexColor("#2563eb")
                chart.lines[0].strokeWidth = 2
                drawing.add(chart)
            else:
                chart = VerticalBarChart()
                chart.x = 45
                chart.y = 35
                chart.width = 450
                chart.height = 190
                chart.data = [numeric_values]
                chart.categoryAxis.categoryNames = labels
                chart.categoryAxis.labels.fontSize = 7
                chart.categoryAxis.labels.angle = 35
                chart.categoryAxis.labels.dy = -15
                chart.valueAxis.valueMin = 0
                chart.valueAxis.valueMax = max(numeric_values) * 1.1 if max(numeric_values) else 1
                chart.bars[0].fillColor = HexColor("#2563eb")
                chart.bars[0].strokeColor = HexColor("#2563eb")
                drawing.add(chart)

            flowables.append(drawing)
            flowables.append(Spacer(1, 12))

        return flowables


business_analytics_service = BusinessAnalyticsService()
