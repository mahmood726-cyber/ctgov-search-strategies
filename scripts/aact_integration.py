#!/usr/bin/env python3
"""
AACT Database Integration
Aggregate Analysis of ClinicalTrials.gov (AACT) PostgreSQL Database

AACT provides:
- Complete CT.gov data in SQL-queryable format
- Daily updates mirroring CT.gov
- Rich relational data (conditions, interventions, outcomes, sponsors)
- Historical snapshots

Database: aact.ctti-clinicaltrials.org
Documentation: https://aact.ctti-clinicaltrials.org/

Author: Mahmood Ahmad
Version: 4.2
"""

import os
import json
import csv
from datetime import datetime, timezone
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

# Try to import psycopg2, fall back to pg8000 if not available
try:
    import psycopg2
    from psycopg2 import sql
    DB_DRIVER = "psycopg2"
except ImportError:
    try:
        import pg8000
        DB_DRIVER = "pg8000"
    except ImportError:
        DB_DRIVER = None
        print("Warning: No PostgreSQL driver found. Install psycopg2 or pg8000.")


@dataclass
class AACTStudy:
    """A study from AACT database"""
    nct_id: str
    brief_title: str
    official_title: str
    overall_status: str
    phase: str
    study_type: str
    enrollment: int
    start_date: str
    completion_date: str
    conditions: List[str] = field(default_factory=list)
    interventions: List[str] = field(default_factory=list)
    primary_outcomes: List[str] = field(default_factory=list)
    sponsors: List[str] = field(default_factory=list)
    countries: List[str] = field(default_factory=list)
    has_results: bool = False
    allocation: str = ""
    primary_purpose: str = ""


class AACTDatabase:
    """
    Interface to AACT PostgreSQL database.

    Connection info (read-only public access):
    - Host: aact.ctti-clinicaltrials.org
    - Port: 5432
    - Database: aact
    - User: (requires registration at https://aact.ctti-clinicaltrials.org/users/sign_up)
    """

    DEFAULT_HOST = "aact.ctti-clinicaltrials.org"
    DEFAULT_PORT = 5432
    DEFAULT_DB = "aact"

    def __init__(self, user: str = None, password: str = None, host: str = None):
        """
        Initialize AACT connection.

        Get credentials by registering at https://aact.ctti-clinicaltrials.org/users/sign_up
        """
        self.host = host or os.environ.get("AACT_HOST", self.DEFAULT_HOST)
        self.port = self.DEFAULT_PORT
        self.database = self.DEFAULT_DB
        self.user = user or os.environ.get("AACT_USER")
        self.password = password or os.environ.get("AACT_PASSWORD")
        self.conn = None

    def connect(self) -> bool:
        """Establish database connection"""
        if not self.user or not self.password:
            print("AACT credentials required. Set AACT_USER and AACT_PASSWORD environment variables")
            print("Register at: https://aact.ctti-clinicaltrials.org/users/sign_up")
            return False

        if DB_DRIVER is None:
            print("No PostgreSQL driver available. Install: pip install psycopg2-binary")
            return False

        try:
            if DB_DRIVER == "psycopg2":
                self.conn = psycopg2.connect(
                    host=self.host,
                    port=self.port,
                    database=self.database,
                    user=self.user,
                    password=self.password,
                    sslmode='require'
                )
            else:  # pg8000
                self.conn = pg8000.connect(
                    host=self.host,
                    port=self.port,
                    database=self.database,
                    user=self.user,
                    password=self.password,
                    ssl_context=True
                )
            print(f"Connected to AACT database at {self.host}")
            return True

        except Exception as e:
            print(f"Connection error: {e}")
            return False

    def disconnect(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None

    def search_by_condition(
        self,
        condition: str,
        study_type: str = "Interventional",
        allocation: str = None,
        status: str = None,
        limit: int = 1000
    ) -> List[AACTStudy]:
        """
        Search studies by condition using SQL.

        Much more powerful than API - can filter on any field.
        """
        if not self.conn:
            if not self.connect():
                return []

        cursor = self.conn.cursor()

        # Build query with optional filters
        query = """
            SELECT DISTINCT
                s.nct_id,
                s.brief_title,
                s.official_title,
                s.overall_status,
                s.phase,
                s.study_type,
                s.enrollment,
                s.start_date,
                s.completion_date,
                d.allocation,
                d.primary_purpose,
                CASE WHEN r.nct_id IS NOT NULL THEN true ELSE false END as has_results
            FROM ctgov.studies s
            LEFT JOIN ctgov.designs d ON s.nct_id = d.nct_id
            LEFT JOIN ctgov.reported_events r ON s.nct_id = r.nct_id
            JOIN ctgov.conditions c ON s.nct_id = c.nct_id
            WHERE LOWER(c.name) LIKE LOWER(%s)
        """

        params = [f"%{condition}%"]

        if study_type:
            query += " AND s.study_type = %s"
            params.append(study_type)

        if allocation:
            query += " AND d.allocation = %s"
            params.append(allocation)

        if status:
            query += " AND s.overall_status = %s"
            params.append(status)

        query += f" LIMIT {limit}"

        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()

            studies = []
            for row in rows:
                study = AACTStudy(
                    nct_id=row[0],
                    brief_title=row[1] or "",
                    official_title=row[2] or "",
                    overall_status=row[3] or "",
                    phase=row[4] or "",
                    study_type=row[5] or "",
                    enrollment=row[6] or 0,
                    start_date=str(row[7]) if row[7] else "",
                    completion_date=str(row[8]) if row[8] else "",
                    allocation=row[9] or "",
                    primary_purpose=row[10] or "",
                    has_results=row[11] or False
                )
                studies.append(study)

            return studies

        except Exception as e:
            print(f"Query error: {e}")
            return []

    def get_study_details(self, nct_id: str) -> Optional[AACTStudy]:
        """Get full details for a single study"""
        if not self.conn:
            if not self.connect():
                return None

        cursor = self.conn.cursor()

        try:
            # Get basic study info
            cursor.execute("""
                SELECT
                    s.nct_id, s.brief_title, s.official_title,
                    s.overall_status, s.phase, s.study_type,
                    s.enrollment, s.start_date, s.completion_date,
                    d.allocation, d.primary_purpose
                FROM ctgov.studies s
                LEFT JOIN ctgov.designs d ON s.nct_id = d.nct_id
                WHERE s.nct_id = %s
            """, [nct_id])

            row = cursor.fetchone()
            if not row:
                return None

            study = AACTStudy(
                nct_id=row[0],
                brief_title=row[1] or "",
                official_title=row[2] or "",
                overall_status=row[3] or "",
                phase=row[4] or "",
                study_type=row[5] or "",
                enrollment=row[6] or 0,
                start_date=str(row[7]) if row[7] else "",
                completion_date=str(row[8]) if row[8] else "",
                allocation=row[9] or "",
                primary_purpose=row[10] or ""
            )

            # Get conditions
            cursor.execute(
                "SELECT name FROM ctgov.conditions WHERE nct_id = %s",
                [nct_id]
            )
            study.conditions = [r[0] for r in cursor.fetchall()]

            # Get interventions
            cursor.execute(
                "SELECT intervention_type, name FROM ctgov.interventions WHERE nct_id = %s",
                [nct_id]
            )
            study.interventions = [f"{r[0]}: {r[1]}" for r in cursor.fetchall()]

            # Get primary outcomes
            cursor.execute(
                "SELECT measure FROM ctgov.outcomes WHERE nct_id = %s AND outcome_type = 'primary'",
                [nct_id]
            )
            study.primary_outcomes = [r[0] for r in cursor.fetchall()]

            # Get sponsors
            cursor.execute(
                "SELECT name FROM ctgov.sponsors WHERE nct_id = %s",
                [nct_id]
            )
            study.sponsors = [r[0] for r in cursor.fetchall()]

            # Get countries
            cursor.execute(
                "SELECT DISTINCT country FROM ctgov.facilities WHERE nct_id = %s",
                [nct_id]
            )
            study.countries = [r[0] for r in cursor.fetchall() if r[0]]

            # Check for results
            cursor.execute(
                "SELECT COUNT(*) FROM ctgov.reported_events WHERE nct_id = %s",
                [nct_id]
            )
            study.has_results = cursor.fetchone()[0] > 0

            return study

        except Exception as e:
            print(f"Query error: {e}")
            return None

    def validate_nct_exists(self, nct_ids: List[str]) -> Dict[str, bool]:
        """Check which NCT IDs exist in database"""
        if not self.conn:
            if not self.connect():
                return {}

        cursor = self.conn.cursor()

        try:
            # Check all at once
            placeholders = ','.join(['%s'] * len(nct_ids))
            cursor.execute(
                f"SELECT nct_id FROM ctgov.studies WHERE nct_id IN ({placeholders})",
                nct_ids
            )

            found = set(r[0] for r in cursor.fetchall())
            return {nct: nct in found for nct in nct_ids}

        except Exception as e:
            print(f"Query error: {e}")
            return {}

    def get_rcts_with_results(self, condition: str, limit: int = 500) -> List[AACTStudy]:
        """Get RCTs that have posted results - good for validation"""
        if not self.conn:
            if not self.connect():
                return []

        cursor = self.conn.cursor()

        query = """
            SELECT DISTINCT
                s.nct_id, s.brief_title, s.official_title,
                s.overall_status, s.phase, s.study_type,
                s.enrollment, s.start_date, s.completion_date,
                d.allocation, d.primary_purpose
            FROM ctgov.studies s
            JOIN ctgov.designs d ON s.nct_id = d.nct_id
            JOIN ctgov.conditions c ON s.nct_id = c.nct_id
            JOIN ctgov.reported_events r ON s.nct_id = r.nct_id
            WHERE LOWER(c.name) LIKE LOWER(%s)
              AND s.study_type = 'Interventional'
              AND d.allocation = 'Randomized'
            LIMIT %s
        """

        try:
            cursor.execute(query, [f"%{condition}%", limit])
            rows = cursor.fetchall()

            studies = []
            for row in rows:
                study = AACTStudy(
                    nct_id=row[0],
                    brief_title=row[1] or "",
                    official_title=row[2] or "",
                    overall_status=row[3] or "",
                    phase=row[4] or "",
                    study_type=row[5] or "",
                    enrollment=row[6] or 0,
                    start_date=str(row[7]) if row[7] else "",
                    completion_date=str(row[8]) if row[8] else "",
                    allocation=row[9] or "",
                    primary_purpose=row[10] or "",
                    has_results=True
                )
                studies.append(study)

            return studies

        except Exception as e:
            print(f"Query error: {e}")
            return []

    def search_strategy_sql(self, condition: str, strategy: str) -> str:
        """
        Get SQL equivalent of each search strategy.
        This allows precise replication of API searches.
        """
        base_query = """
            SELECT DISTINCT s.nct_id
            FROM ctgov.studies s
            JOIN ctgov.conditions c ON s.nct_id = c.nct_id
            LEFT JOIN ctgov.designs d ON s.nct_id = d.nct_id
            WHERE LOWER(c.name) LIKE LOWER('%{condition}%')
        """

        strategies = {
            "S1": base_query,  # Condition only
            "S2": base_query + " AND s.study_type = 'Interventional'",
            "S3": base_query + " AND d.allocation = 'Randomized'",
            "S6": base_query + " AND s.overall_status = 'Completed'",
            "S10": base_query + " AND d.allocation = 'Randomized' AND d.primary_purpose = 'Treatment'"
        }

        return strategies.get(strategy, base_query).format(condition=condition)


# =============================================================================
# AACT-BASED VALIDATION
# =============================================================================

class AACTValidator:
    """Validate search strategies using AACT database"""

    def __init__(self, user: str = None, password: str = None):
        self.db = AACTDatabase(user=user, password=password)

    def validate_search_strategy(
        self,
        gold_standard_ncts: List[str],
        strategy: str = "S1"
    ) -> Dict:
        """
        Validate a search strategy using AACT.

        For each NCT ID in gold standard:
        1. Get its condition(s) from AACT
        2. Run strategy SQL query for that condition
        3. Check if NCT ID appears in results
        """
        if not self.db.connect():
            return {"error": "Could not connect to AACT"}

        results = {
            "strategy": strategy,
            "total_tested": 0,
            "found": 0,
            "not_found": 0,
            "invalid": 0,
            "details": []
        }

        cursor = self.db.conn.cursor()

        for nct_id in gold_standard_ncts:
            # Get condition for this NCT
            try:
                cursor.execute(
                    "SELECT name FROM ctgov.conditions WHERE nct_id = %s LIMIT 1",
                    [nct_id]
                )
                row = cursor.fetchone()

                if not row:
                    results["invalid"] += 1
                    continue

                condition = row[0]
                results["total_tested"] += 1

                # Run strategy query
                strategy_sql = self.db.search_strategy_sql(condition, strategy)
                cursor.execute(strategy_sql)
                found_ncts = set(r[0] for r in cursor.fetchall())

                if nct_id in found_ncts:
                    results["found"] += 1
                    results["details"].append({
                        "nct_id": nct_id,
                        "condition": condition,
                        "status": "found"
                    })
                else:
                    results["not_found"] += 1
                    results["details"].append({
                        "nct_id": nct_id,
                        "condition": condition,
                        "status": "not_found"
                    })

            except Exception as e:
                results["invalid"] += 1

        self.db.disconnect()

        # Calculate metrics
        if results["total_tested"] > 0:
            recall = results["found"] / results["total_tested"]
            results["recall"] = round(recall, 4)
            results["recall_pct"] = f"{recall:.1%}"

        return results


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="AACT Database Integration")
    subparsers = parser.add_subparsers(dest="command")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search AACT by condition")
    search_parser.add_argument("condition", help="Condition to search")
    search_parser.add_argument("--rct", action="store_true", help="Only RCTs")
    search_parser.add_argument("--results", action="store_true", help="Only with results")
    search_parser.add_argument("-n", "--limit", type=int, default=100)
    search_parser.add_argument("-o", "--output", help="Output JSON file")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate NCT IDs exist")
    validate_parser.add_argument("nct_ids", nargs="+", help="NCT IDs to validate")

    # Details command
    details_parser = subparsers.add_parser("details", help="Get study details")
    details_parser.add_argument("nct_id", help="NCT ID")

    args = parser.parse_args()

    # Check for credentials
    if not os.environ.get("AACT_USER"):
        print("=" * 60)
        print("AACT Database Credentials Required")
        print("=" * 60)
        print("\n1. Register at: https://aact.ctti-clinicaltrials.org/users/sign_up")
        print("2. Set environment variables:")
        print("   export AACT_USER=your_username")
        print("   export AACT_PASSWORD=your_password")
        print("\nAlternatively, the tool can work without AACT using CT.gov API.")
        return

    db = AACTDatabase()

    if args.command == "search":
        if args.results:
            studies = db.get_rcts_with_results(args.condition, args.limit)
        elif args.rct:
            studies = db.search_by_condition(
                args.condition,
                allocation="Randomized",
                limit=args.limit
            )
        else:
            studies = db.search_by_condition(args.condition, limit=args.limit)

        print(f"Found {len(studies)} studies")
        for study in studies[:10]:
            print(f"  {study.nct_id}: {study.brief_title[:50]}...")

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump([{
                    "nct_id": s.nct_id,
                    "title": s.brief_title,
                    "status": s.overall_status,
                    "phase": s.phase,
                    "enrollment": s.enrollment,
                    "has_results": s.has_results
                } for s in studies], f, indent=2)
            print(f"Saved to {args.output}")

    elif args.command == "validate":
        results = db.validate_nct_exists(args.nct_ids)
        for nct, exists in results.items():
            status = "FOUND" if exists else "NOT FOUND"
            print(f"  {nct}: {status}")

    elif args.command == "details":
        study = db.get_study_details(args.nct_id)
        if study:
            print(f"NCT ID: {study.nct_id}")
            print(f"Title: {study.brief_title}")
            print(f"Status: {study.overall_status}")
            print(f"Phase: {study.phase}")
            print(f"Enrollment: {study.enrollment}")
            print(f"Conditions: {', '.join(study.conditions)}")
            print(f"Interventions: {', '.join(study.interventions[:3])}")
            print(f"Primary Outcomes: {', '.join(study.primary_outcomes[:2])}")
            print(f"Has Results: {study.has_results}")
        else:
            print(f"Study {args.nct_id} not found")

    db.disconnect()


if __name__ == "__main__":
    main()
