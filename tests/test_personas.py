"""Persona walkthrough integration tests: recruiter, business owner, individual."""

from __future__ import annotations

import json

import pytest

from mdm_mcp.services.dataset_service import DatasetService
from mdm_mcp.services.file_service import FileService
from mdm_mcp.services.row_service import RowService


def make_services(repo):
    repo  # keep fixture reference
    return DatasetService(repo), RowService(repo), FileService(repo)


def test_recruiter_walkthrough(repo, tmp_path):
    """One dataset per JD, bulk import of applicants, typo-tolerant search, stage funnel."""
    svc, rows, files = make_services(repo)
    svc.create_dataset("Java JD Candidates", "Applicants for the Senior Java role", [
        {"name": "name", "type": "string", "required": True},
        {"name": "phone", "type": "phone"},
        {"name": "experience", "type": "float", "min_value": 0},
        {"name": "stage", "type": "enum", "options": ["Applied", "Screened", "Interviewed", "Rejected"]},
        {"name": "applied_on", "type": "date"},
    ])

    csv_file = tmp_path / "applicants.csv"
    csv_file.write_text(
        "name,phone,experience,stage,applied_on\n"
        "Rahul Sharma,9876543210,5.5,Applied,2026-08-20\n"
        "Priya Menon,+919812345678,3,Applied,2026-08-21\n"
        "Vikram Rao,9876500000,x,Applied,2026-08-21\n",
        encoding="utf-8",
    )
    preview = files.import_rows("Java JD Candidates", str(csv_file), "auto", confirm=False)
    assert preview["preview"]["row_count"] == 3
    imported = files.import_rows("Java JD Candidates", str(csv_file), "auto", confirm=True)
    assert imported["added"] == 2 and imported["rejected"] == 1
    assert any("Indian mobile" in e or "must be" in e for e in imported["rejected_rows"][0]["errors"])

    found = rows.search_rows("Java JD Candidates", fuzzy=True, query="Rahual", fuzzy_columns=["name"])
    assert found["total"] == 1 and found["rows"][0]["name"] == "Rahul Sharma"

    funnel = rows.search_rows(
        "Java JD Candidates",
        conditions=[
            {"column": "stage", "op": "eq", "value": "Applied"},
            {"column": "experience", "op": "gte", "value": 3},
        ],
        sort_by="experience",
        sort_order="desc",
    )
    assert [r["name"] for r in funnel["rows"]] == ["Rahul Sharma", "Priya Menon"]

    shortlisted = rows.update_rows(
        "Java JD Candidates",
        {"stage": "Screened"},
        row_ids=[r["id"] for r in funnel["rows"]],
    )
    assert shortlisted["updated"] == 2

    summary = rows.summarize_dataset("Java JD Candidates")
    assert summary["enums"]["stage"] == {"Screened": 2}
    assert summary["numeric"]["experience"]["sum"] == 8.5


def test_business_owner_walkthrough(repo):
    """Inventory + vendors datasets, combined filters, bulk restock marking, totals."""
    svc, rows, _ = make_services(repo)
    svc.create_dataset("Inventory", "Stock on hand", [
        {"name": "item", "type": "string", "required": True},
        {"name": "quantity", "type": "integer", "min_value": 0},
        {"name": "price", "type": "float", "min_value": 0},
        {"name": "vendor", "type": "enum", "options": ["Acme", "GlobalTraders", "LocalHub"]},
    ])
    svc.create_dataset("Vendors", "Supplier contacts", [
        {"name": "name", "type": "string", "required": True},
        {"name": "phone", "type": "phone"},
        {"name": "city", "type": "string"},
    ])
    rows.add_rows("Vendors", [
        {"name": "Acme Traders", "phone": "9812345670", "city": "Delhi"},
        {"name": "Global Traders", "phone": "9812345671", "city": "Mumbai"},
    ])
    rows.add_rows("Inventory", [
        {"item": "Chair", "quantity": 40, "price": 1200, "vendor": "Acme"},
        {"item": "Table", "quantity": 8, "price": 4500, "vendor": "GlobalTraders"},
        {"item": "Lamp", "quantity": 5, "price": 700, "vendor": "LocalHub"},
        {"item": "Desk", "quantity": 12, "price": 6000, "vendor": "GlobalTraders"},
    ])

    low_stock = rows.search_rows("Inventory", conditions=[
        {"column": "quantity", "op": "lt", "value": 10},
        {"column": "vendor", "op": "ne", "value": "Acme"},
    ])
    assert {r["item"] for r in low_stock["rows"]} == {"Table", "Lamp"}

    restocked = rows.update_rows("Inventory", {"quantity": 25}, conditions=[
        {"column": "item", "op": "in", "value": ["Table", "Lamp"]},
    ], dry_run=True)
    assert restocked["preview"]["count"] == 2
    applied = rows.update_rows("Inventory", {"quantity": 25}, conditions=[
        {"column": "item", "op": "in", "value": ["Table", "Lamp"]},
    ], dry_run=False)
    assert applied["updated"] == 2

    summary = rows.summarize_dataset("Inventory")
    assert summary["numeric"]["quantity"]["sum"] == 40 + 25 + 25 + 12
    assert summary["numeric"]["price"]["sum"] == 1200 + 4500 + 700 + 6000
    assert summary["enums"]["vendor"] == {"Acme": 1, "GlobalTraders": 2, "LocalHub": 1}

    vendor_lookup = rows.search_rows("Vendors", fuzzy=True, query="Globl Traders", fuzzy_columns=["name"])
    assert vendor_lookup["total"] >= 1
    assert vendor_lookup["rows"][0]["name"] == "Global Traders"
    assert vendor_lookup["rows"][0]["city"] == "Mumbai"


def test_individual_walkthrough(repo):
    """Daily health log: date-heavy entries, validation pre-checks, range search."""
    svc, rows, _ = make_services(repo)
    svc.create_dataset("Health Log", "Daily tracking", [
        {"name": "date", "type": "date", "required": True},
        {"name": "weight_kg", "type": "float", "min_value": 20, "max_value": 250},
        {"name": "meditated", "type": "boolean"},
        {"name": "mood", "type": "enum", "options": ["Good", "OK", "Low"]},
        {"name": "notes", "type": "text"},
    ])

    precheck = rows.validate_rows("Health Log", [
        {"date": "2026-08-24", "weight_kg": "72.5", "meditated": "true", "mood": "Good"},
        {"date": "24-08-2026", "weight_kg": 72, "meditated": False, "mood": "OK"},
        {"date": "2026-08-25", "weight_kg": 500, "meditated": True, "mood": "Great"},
    ])
    assert precheck["valid"] == 1 and precheck["invalid"] == 2
    assert precheck["results"][0]["normalized"]["meditated"] is True

    week = [
        {"date": f"2026-08-{day}", "weight_kg": weight, "meditated": day in {"24", "26"}, "mood": mood}
        for day, weight, mood in [
            ("24", 72.5, "Good"), ("25", 72.4, "OK"), ("26", 72.2, "Good"),
            ("27", 72.3, "Low"), ("28", 72.1, "OK"), ("29", 71.9, "Good"), ("30", 71.8, "Good"),
        ]
    ]
    added = rows.add_rows("Health Log", week)
    assert added["added"] == 7

    trend = rows.search_rows(
        "Health Log",
        conditions=[{"column": "date", "op": "between", "value": ["2026-08-26", "2026-08-30"]}],
        sort_by="date",
        sort_order="desc",
        columns=["date", "weight_kg", "mood"],
    )
    assert trend["total"] == 5
    assert trend["rows"][0]["date"] == "2026-08-30"

    summary = rows.summarize_dataset("Health Log")
    assert summary["numeric"]["weight_kg"]["count"] == 7
    assert summary["enums"]["mood"] == {"Good": 4, "OK": 2, "Low": 1}

    missed = rows.search_rows("Health Log", conditions=[{"column": "meditated", "op": "eq", "value": False}])
    assert missed["total"] == 5
