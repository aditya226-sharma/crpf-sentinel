"""Synthetic Criminal-Intelligence demo records (source: ``case_record``).

ALL DATA IS FABRICATED. Nothing here is real case data — every name, phone,
vehicle, account, and amount is invented for the SIH26156 demo. Records are
pushed through the SAME ingest pipeline (ParserRegistry → normalize → store →
graph index) so the two dashboards always reflect what the parser genuinely
produced.

Plot (synthetic, for the demo walkthrough): a timber-smuggling ring operates
around the Punjab / Rajasthan border. Most case files look disconnected, but
two distant records secretly share ONE phone number — the "hidden nexus" the
Criminal Intelligence graph's path query exposes.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.log import Log

HIDDEN_PHONE = "+91 98270 44219"

PERSONS = [
    ("Ramesh Patil", ["+91 98111 22334"], ["PB-02-CX-7721"], ["IFSC PUNB0123456 50012000111"]),
    ("Imran Qureshi", ["+91 98256 77889"], ["PB-29-BT-4410"], ["IFSC UTIB0001234 91803209445"]),
    ("Kuldeep Randhawa", ["+91 98140 55667"], ["CH-01-JM-8891"], ["IFSC SBIN0008871 30100456721"]),
    ("Sarabjit Gill", ["+91 99114 33221"], ["PB-65-DL-1102"], ["IFSC HDFC0002211 50200011987"]),
    ("Vijay Shirke", ["+91 99301 44556"], ["MH-12-AB-3321"], ["IFSC ICIC0000987 11234560001"]),
    ("Ashish Thakur", ["+91 98105 99887"], ["DL-03-CD-8821"], ["IFSC PUNB0112234 50022100999"]),
    ("Mohd Faisal", ["+91 97001 55443"], ["RJ-19-DA-2209"], ["IFSC BARB0JAI345 90801122334"]),
    ("Gurpreet Bhullar", ["+91 70152 88990"], ["PB-02-CX-9910"], ["IFSC PUNB0012345 50033211876"]),
    ("Nitin Khopde", ["+91 90090 11223"], ["MH-14-KB-7720"], ["IFSC CNRB0000045 1177448899"]),
    ("Raju Salunkhe", ["+91 98220 33445"], ["MH-12-RA-6610"], ["IFSC YESB0000111 0033221144"]),
    ("Sandeep Negi", ["+91 98189 77665"], ["UK-07-AB-1190"], ["IFSC SBIN0005522 30455678912"]),
    ("Prakash Yadav", ["+91 98670 44551"], ["DL-11-XY-2203"], ["IFSC ANDB0001221 12345678901"]),
    ("Ravi Solanki", ["+91 98980 66112"], ["GJ-01-QR-5512"], ["IFSC SBIN0001199 31122004590"]),
    ("Manoj Sahu", ["+91 98271 99002"], ["OD-02-CD-3310"], ["IFSC PUNB0233901 50109987650"]),
    ("Kiran Walia", ["+91 97799 80331"], ["CH-01-KW-4411"], ["IFSC YESB0000222 0044332211"]),
    ("Sanjay Dhamija", ["+91 87200 11886"], ["HR-26-TR-7702"], ["IFSC PUNB0128765 61109928371"]),
    ("Rohit Khandekar", ["+91 99307 44112"], ["MH-01-KD-9903"], ["IFSC HDFC0001122 50120447761"]),
    ("Farhan Ali", ["+91 98198 22331"], ["RJ-14-AL-5561"], ["IFSC UTIB0002765 92117083456"]),
    ("Bhupinder Singh", ["+91 98882 11003"], ["PB-65-BP-7716"], ["IFSC SBIN0002233 30555126890"]),
    ("Deepak Lodhi", ["+91 90260 55471"], ["MP-04-LD-2211"], ["IFSC BARB0BHOPAL 90803455010"]),
]

# Fictional officers authoring the records.
OFFICERS = [
    "Insp. A. K. Sinha",
    "SI P. Verma",
    "Insp. D. R. Pandey",
    "SI R. S. Gill",
    "DySP L. N. Sharma",
    "Insp. T. V. Menon",
]

LOCATIONS = [
    ("Chandigarh", "Sector 22 Police Station, Chandigarh"),
    ("New Delhi", "NDLS Yard, New Delhi"),
    ("Amritsar", "Attari Border Checkpost, Amritsar"),
    ("Jaisalmer", "Thar Range, Jaisalmer"),
    ("Mundra", "Mundra Port Gate 3, Gujarat"),
    ("Mumbai", "Dockyard Road, Mumbai"),
    ("Jodhpur", "Soorsagar Station, Jodhpur"),
    ("Ludhiana", "Samrala Chowk, Ludhiana"),
    ("Delhi", "Mehrauli Depot, Delhi"),
    ("Kolkata", "Kidderpore Container Depot"),
    ("Sukhna", "Sukhna Lake Shore, Chandigarh"),
]

AMOUNTS = [48000, 150000, 220000, 90000, 330000, 78000, 210000, 60000, 125000, 275000]
AMOUNT_NAMES = ["payment instalment", "advance against delivery", "settlement of truck hire", "consignment advance"]

TIMELINE = [
    "2026-01-11T08:30:00Z",
    "2026-01-24T10:05:00Z",
    "2026-02-06T09:20:00Z",
    "2026-02-19T14:40:00Z",
    "2026-03-03T07:55:00Z",
    "2026-03-18T11:30:00Z",
    "2026-04-02T13:25:00Z",
    "2026-04-15T06:50:00Z",
    "2026-05-01T17:10:00Z",
    "2026-05-19T09:05:00Z",
    "2026-06-04T12:45:00Z",
    "2026-06-21T08:15:00Z",
    "2026-07-07T15:35:00Z",
    "2026-07-23T18:20:00Z",
    "2026-08-09T10:40:00Z",
]


def _record(
    case_id: str,
    record_type: str,
    date: str,
    officer: str,
    city: str,
    address: str,
    text: str,
    persons: list[str],
    phones: list[str],
    vehicles: list[str] | None = None,
    accounts: list[str] | None = None,
    amount: int | None = None,
) -> dict:
    return {
        "case_id": case_id,
        "record_type": record_type,
        "date": date,
        "officer": officer,
        "unit_code": city,
        "summary": text,
        "persons": persons,
        "phones": phones,
        "addresses": [address],
        "vehicles": vehicles or [],
        "accounts": accounts or [],
        "amount": amount,
        "currency": "INR",
    }


def _build_records() -> list[dict]:
    records: list[dict] = []
    idx = 0
    ts = TIMELINE

    def next_idx() -> int:
        nonlocal idx
        idx += 1
        return idx

    # Phase 1 — border-region intel and FIRs (North India).
    intel_1 = _record(
        f"INT-{next_idx():04d}", "fir", ts[0], OFFICERS[0], "Chandigarh",
        LOCATIONS[0][1],
        "Patrolled Sukhna Lake shore area. Two unidentified men (one with grey jacket) "
        "were seen loading wooden planks into a steel-grey truck near a private jetty; "
        "no number plate on truck. Intelligence suspect timber movement to northern metro depots.",
        [PERSONS[2][0]], [PERSONS[2][1][0]], vehicles=[PERSONS[2][2][0]],
    )
    records.append(intel_1)

    records.append(
        _record(
            f"FIR-{next_idx():04d}", "fir", ts[1], OFFICERS[1], "Amritsar",
            LOCATIONS[2][1],
            "Routine interception of truck PB-02-CX-7721 at Attari checkpost; driver identified "
            "as Ramesh Patil. Cargo declared as household wood but weight mismatch noted; "
            "consignment seized for detailed examination.",
            [PERSONS[0][0]], [PERSONS[0][1][0]], vehicles=[PERSONS[0][2][0]], accounts=[PERSONS[0][3][0]],
        )
    )

    records.append(
        _record(
            f"CDR-{next_idx():04d}", "cdr", ts[2], OFFICERS[2], "Ludhiana",
            LOCATIONS[7][1],
            "Call detail sweep: frequent late-night calls between two high-activity prepaid "
            "numbers associated with timber depots in Ludhiana and Amritsar.",
            [PERSONS[0][0], PERSONS[5][0]],
            [PERSONS[0][1][0], PERSONS[5][1][0]],
        )
    )

    records.append(
        _record(
            f"FIN-{next_idx():04d}", "transaction", ts[3], OFFICERS[3], "Chandigarh",
            LOCATIONS[0][1],
            f"Bank alert: {AMOUNT_NAMES[0]} of INR {AMOUNTS[0]:,} credited to account of Kuldeep "
            "Randhawa hours before the Sukhna intel hit. Source account traced to a Ludhiana timber trader.",
            [PERSONS[2][0], PERSONS[0][0]], [PERSONS[2][1][0]],
            accounts=[PERSONS[2][3][0]], amount=AMOUNTS[0],
        )
    )

    # Phase 2 — expanding the ring across Gujarat and MP.
    records.append(
        _record(
            f"INT-{next_idx():04d}", "fir", ts[4], OFFICERS[4], "Mundra",
            LOCATIONS[4][1],
            "Fishing trawler IR-17 moved pallets from a parked truck (MH-12-AB-3321) at Gate 3 before "
            "dawn. Crew gave conflicting statements; samples logged. Vendor contact number ends -4456.",
            [PERSONS[5][0]], [PERSONS[5][1][0]], vehicles=[PERSONS[5][2][0]],
        )
    )

    records.append(
        _record(
            f"FIR-{next_idx():04d}", "fir", ts[5], OFFICERS[5], "Mumbai",
            LOCATIONS[5][1],
            "Seized crate lot at Dockyard Road warehouse; NHV timber without e-way documentation. "
            "Warehouse lessee identified as Vijay Shirke (A/C 11234560001).",
            [PERSONS[5][0]], [PERSONS[5][1][0]], accounts=[PERSONS[5][3][0]],
        )
    )

    records.append(
        _record(
            f"FIN-{next_idx():04d}", "transaction", ts[6], OFFICERS[0], "Delhi",
            LOCATIONS[3][1],
            f"Transaction INR {AMOUNTS[1]:,} routed from Mundra-linked account to New Delhi depot "
            "account one day before arrival of rail rake."
            " Booked as {AMOUNT_NAMES[1]}.",
            [PERSONS[5][0], PERSONS[6][0]], [PERSONS[6][1][0]],
            accounts=[PERSONS[5][3][0], PERSONS[6][3][0]], amount=AMOUNTS[1],
        )
    )

    records.append(
        _record(
            f"FIR-{next_idx():04d}", "fir", ts[7], OFFICERS[1], "Jodhpur",
            LOCATIONS[6][1],
            "Forest check intercepted jeep RJ-19-DA-2209 carrying recovered teak logs; occupants "
            "fled on foot. Registered owner Mohd Faisal under scanner.",
            [PERSONS[7][0]], [PERSONS[7][1][0]], vehicles=[PERSONS[7][2][0]],
        )
    )

    # Phase 3 — the "hidden nexus": record ~on net yet distant, shares HIDDEN_PHONE.
    records.append(
        _record(
            f"INT-{next_idx():04d}", "fir", ts[8], OFFICERS[2], "Jaisalmer",
            LOCATIONS[3][1],
            "Intel input: an unregistered caller (number +91 98270 44219) coordinates loading of "
            "''transit consignments'' at Thar staging points. No name given. Coordinate with "
            "Rajasthan range patrolling.",
            ["Unknown Caller"], [HIDDEN_PHONE],
        )
    )

    records.append(
        _record(
            f"FIN-{next_idx():04d}", "transaction", ts[9], OFFICERS[3], "Kolkata",
            LOCATIONS[9][1],
            f"Next-day transfer INR {AMOUNTS[2]:,} debited from Surabhi Traders A/C and credited to "
            "two accounts within minutes; flagged duplicate-beneficiary pattern. Labeled "
            f"{AMOUNT_NAMES[2]}.",
            [PERSONS[9][0], PERSONS[10][0]], [PERSONS[9][1][0]],
            accounts=[PERSONS[9][3][0], PERSONS[10][3][0]], amount=AMOUNTS[2],
        )
    )

    # A distant, otherwise-unrelated FIR that secretly shares the same phone
    # (Gurpreet Bhullar's roadside abandoned-load report).
    records.append(
        _record(
            f"FIR-{next_idx():04d}", "fir", ts[10], OFFICERS[4], "Amritsar",
            LOCATIONS[2][1],
            "Truck driver (Gurpreet Bhullar) reported a load book found abandoned near Attari with "
            "receipts referencing a number +91 98270 44219 alongside heavy-vehicle hire notes. "
            "Truck plate PB-02-CX-9910; no cargo recovered.",
            [PERSONS[8][0]], [HIDDEN_PHONE], vehicles=[PERSONS[8][2][0]],
        )
    )

    # Phase 4 — arrests and connected seizures.
    records.append(
        _record(
            f"FIR-{next_idx():04d}", "fir", ts[11], OFFICERS[5], "Amritsar",
            LOCATIONS[2][1],
            "Arrest of Imran Qureshi near Attari with 420 kg processed timber; phones recovered "
            "matched earlier CDR sweep. Consignment traced to Ramesh Patil's earlier pickup.",
            [PERSONS[1][0]], [PERSONS[1][1][0]], vehicles=[PERSONS[1][2][0]],
            accounts=[PERSONS[1][3][0]],
        )
    )

    records.append(
        _record(
            f"FIN-{next_idx():04d}", "transaction", ts[12], OFFICERS[0], "Jodhpur",
            LOCATIONS[6][1],
            f"Escrow INR {AMOUNTS[3]:,} released to Bhupinder Singh for ransport of seized stock. "
            f"Disbursal flagged as {AMOUNT_NAMES[3]} for Ravi Solanki network.",
            [PERSONS[11][0], PERSONS[12][0]], [PERSONS[12][1][0]],
            accounts=[PERSONS[11][3][0]], amount=AMOUNTS[3],
        )
    )

    records.append(
        _record(
            f"CDR-{next_idx():04d}", "cdr", ts[13], OFFICERS[1], "Chandigarh",
            LOCATIONS[0][1],
            "CDR overlay of recovered phones: Sanjay Dhamija and Kiran Walia numbers overlap the "
            "Chandigarh cell tower used on Sukhna incident day.",
            [PERSONS[14][0], PERSONS[15][0]], [PERSONS[14][1][0], PERSONS[15][1][0]],
        )
    )

    records.append(
        _record(
            f"FIR-{next_idx():04d}", "fir", ts[14], OFFICERS[2], "Delhi",
            LOCATIONS[8][1],
            "Raid on Mehrauli Depot recovered 1.2 MT timber with NHV markings; watchman identified "
            "Deepak Lodhi as operator. Depot phone records flagged for further linkage.",
            [PERSONS[19][0]], [PERSONS[19][1][0]], vehicles=[PERSONS[19][2][0]],
            accounts=[PERSONS[19][3][0]],
        )
    )

    # Bulk filler so the dashboard has a rich timeline and healthy graph density:
    # deterministic sequences over the pools (no randomness).
    filler_types = [
        ("INT", "fir"),
        ("FIR", "fir"),
        ("CDR", "cdr"),
        ("FIN", "transaction"),
        ("FIR", "fir"),
        ("CDR", "cdr"),
    ]
    n = 0
    for i in range(160):
        kind, rtype = filler_types[i % len(filler_types)]
        person = PERSONS[i % len(PERSONS)]
        prev = PERSONS[(i + 7) % len(PERSONS)]
        city, address = LOCATIONS[i % len(LOCATIONS)]
        date = TIMELINE[i % len(TIMELINE)]
        officer = OFFICERS[i % len(OFFICERS)]
        case = f"{kind}-{2600 + n:04d}"
        n += 1
        if rtype == "cdr":
            records.append(
                _record(
                    case, rtype, date, officer, city, address,
                    f"Call detail extract for probe around {city}: repeated contact between "
                    f"{person[0]} side numbers and {prev[0]} side numbers over 45 days.",
                    [person[0], prev[0]], [person[1][0], prev[1][0]],
                )
            )
        elif rtype == "transaction":
            amount = AMOUNTS[i % len(AMOUNTS)]
            name = AMOUNT_NAMES[i % len(AMOUNT_NAMES)]
            records.append(
                _record(
                    case, rtype, date, officer, city, address,
                    f"Financial intelligence: INR {amount:,} sent as {name} "
                    f"(counterparty traced to {prev[0]}) — flag for link analysis.",
                    [person[0], prev[0]], [person[1][0]],
                    accounts=[person[3][0]], amount=amount,
                )
            )
        else:
            thing = ["load of untreated timber", "recovered sandal logs", "night consignment of planks",
                     "transit stock bound for depot", "truck flagged for timber movement"][i % 5]
            records.append(
                _record(
                    case, rtype, date, officer, city, address,
                    f"{kind} record from {city}: {thing} linked to {person[0]}; "
                    f"vehicle {person[2][0]} observed at {address}.",
                    [person[0]], [person[1][0]], vehicles=[person[2][0]],
                )
            )

    return records


def seed_case_records(db: Session) -> int:
    """Seed fiction case records through the real ingest pipeline. Idempotent."""
    existing = db.query(Log).filter(Log.source == "case_record").first()
    if existing is not None:
        return 0

    agent = db.query(Agent).filter(Agent.agent_id == "CASE-CATALOG-SIM").first()
    if agent is None:
        unit = db.query(Agent).filter(Agent.simulated.is_(True)).first()
        unit_id = unit.unit_id if unit else None
        if unit_id is None:
            from app.models.unit import Unit

            first = db.query(Unit).first()
            unit_id = first.id if first else "u-demo"
        agent = Agent(
            id="ca" + "00000000000000",
            agent_id="CASE-CATALOG-SIM",
            unit_id=unit_id,
            hostname="CASE-CATALOG",
            status="offline",
            simulated=True,
        )
        db.add(agent)
        db.flush()

    from app.models.unit import Unit
    from app.services.ingest import ingest_payload

    unit = db.query(Unit).filter(Unit.id == agent.unit_id).first()
    records = _build_records()
    accepted = 0
    for record in records:
        result = ingest_payload(
            db,
            {"data": record},
            agent=agent,
            unit=unit,
            parser_format="case_record",
        )
        if result.get("accepted"):
            accepted += 1
    db.commit()
    return accepted