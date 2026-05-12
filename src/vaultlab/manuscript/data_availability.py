"""Data Availability statements, FAIR checklist, repository registry.

Absorbed from the nature-data skill (Yuan Yizhe, SJTU) at
nature-skills/skills/nature-data/.

For any Nature / Cell / eLife submission, the journal asks for a Data
Availability Statement (DAS) covering every result-supporting dataset:
where it lives, what identifier resolves to it, what restrictions apply,
and how a reader can re-run the analysis. This module ships:

- A registry of common repositories with identifier formats and citation
  templates.
- A FAIR (Findable / Accessible / Interoperable / Reusable) checklist
  with 14 enforceable items.
- Statement-pattern templates for the common scenarios (public deposit,
  restricted access, internal-only, on-request, supplementary, code).

Public API
----------

- :data:`REPOSITORIES` — repository registry
- :data:`FAIR_CHECKLIST` — 14 items per FAIR principle
- :func:`statement_template` — fetch a DAS template by scenario
- :func:`audit_statement` — flag common DAS failures
- :class:`Repository`, :class:`FAIRItem`, :class:`DAScenario`
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


@dataclass(frozen=True)
class Repository:
    """One data repository entry."""

    slug: str
    name: str
    domain: str  # "genomics" / "proteomics" / "imaging" / "structural" / "general"
    identifier_format: str  # e.g. "GSE\\d+"
    url_template: str  # e.g. "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={id}"
    citation_template: str  # for DAS prose


# ---------------------------------------------------------------------------
# Repository registry — domain-mandated repositories first.

REPOSITORIES: dict[str, Repository] = {
    "geo": Repository(
        slug="geo",
        name="NCBI Gene Expression Omnibus (GEO)",
        domain="genomics",
        identifier_format=r"^GSE\d+$",
        url_template="https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={id}",
        citation_template=(
            "RNA-seq and microarray data have been deposited in NCBI Gene "
            "Expression Omnibus (GEO) under accession {id}."
        ),
    ),
    "sra": Repository(
        slug="sra",
        name="NCBI Sequence Read Archive (SRA)",
        domain="genomics",
        identifier_format=r"^(SRP|PRJ[ENA])\w+$",
        url_template="https://www.ncbi.nlm.nih.gov/sra/{id}",
        citation_template="Raw sequencing reads are available from SRA under accession {id}.",
    ),
    "genbank": Repository(
        slug="genbank",
        name="NCBI GenBank",
        domain="genomics",
        identifier_format=r"^[A-Z]{1,3}\d+(\.\d+)?$",
        url_template="https://www.ncbi.nlm.nih.gov/nuccore/{id}",
        citation_template="Sequences are available in GenBank under accession {id}.",
    ),
    "ena": Repository(
        slug="ena",
        name="European Nucleotide Archive (ENA)",
        domain="genomics",
        identifier_format=r"^PRJEB\d+$",
        url_template="https://www.ebi.ac.uk/ena/browser/view/{id}",
        citation_template="Sequencing data are available from ENA under accession {id}.",
    ),
    "pride": Repository(
        slug="pride",
        name="PRIDE Proteomics Identifications",
        domain="proteomics",
        identifier_format=r"^PXD\d+$",
        url_template="https://www.ebi.ac.uk/pride/archive/projects/{id}",
        citation_template="Proteomics data have been deposited in PRIDE under accession {id}.",
    ),
    "massive": Repository(
        slug="massive",
        name="MassIVE",
        domain="proteomics",
        identifier_format=r"^MSV\d+$",
        url_template="https://massive.ucsd.edu/ProteoSAFe/dataset.jsp?accession={id}",
        citation_template="Mass spectrometry data are available from MassIVE under accession {id}.",
    ),
    "pdb": Repository(
        slug="pdb",
        name="Protein Data Bank (PDB)",
        domain="structural",
        identifier_format=r"^[0-9][A-Z0-9]{3}$",
        url_template="https://www.rcsb.org/structure/{id}",
        citation_template="Atomic coordinates are deposited in the PDB under accession {id}.",
    ),
    "empiar": Repository(
        slug="empiar",
        name="EMPIAR (Electron Microscopy Public Image Archive)",
        domain="imaging",
        identifier_format=r"^EMPIAR-\d+$",
        url_template="https://www.ebi.ac.uk/empiar/{id}",
        citation_template="Raw cryo-EM micrographs are available from EMPIAR under accession {id}.",
    ),
    "idr": Repository(
        slug="idr",
        name="Image Data Resource (IDR)",
        domain="imaging",
        identifier_format=r"^idr\d{4}$",
        url_template="https://idr.openmicroscopy.org/webclient/?show=project-{id}",
        citation_template="Imaging datasets are available from IDR under accession {id}.",
    ),
    "ega": Repository(
        slug="ega",
        name="European Genome-phenome Archive (EGA)",
        domain="genomics",
        identifier_format=r"^EGAS\d+$",
        url_template="https://ega-archive.org/studies/{id}",
        citation_template=(
            "Controlled-access human data are deposited in EGA under accession "
            "{id}; access is governed by a Data Access Committee."
        ),
    ),
    "dbgap": Repository(
        slug="dbgap",
        name="dbGaP (NIH)",
        domain="genomics",
        identifier_format=r"^phs\d+(\.v\d+)?(\.p\d+)?$",
        url_template="https://www.ncbi.nlm.nih.gov/projects/gap/cgi-bin/study.cgi?study_id={id}",
        citation_template=(
            "Controlled-access human data are deposited in dbGaP under accession "
            "{id}; access is by Data Access Committee approval."
        ),
    ),
    "dryad": Repository(
        slug="dryad",
        name="Dryad Digital Repository",
        domain="general",
        identifier_format=r"^10\.5061/dryad\.\w+$",
        url_template="https://doi.org/{id}",
        citation_template="Source data are available in the Dryad Digital Repository at https://doi.org/{id}.",
    ),
    "zenodo": Repository(
        slug="zenodo",
        name="Zenodo",
        domain="general",
        identifier_format=r"^10\.5281/zenodo\.\d+$",
        url_template="https://doi.org/{id}",
        citation_template="Source data and analysis code are archived at https://doi.org/{id}.",
    ),
    "osf": Repository(
        slug="osf",
        name="Open Science Framework",
        domain="general",
        identifier_format=r"^[a-z0-9]{5,12}$",
        url_template="https://osf.io/{id}",
        citation_template="Pre-registration and source data are at https://osf.io/{id}.",
    ),
    "github": Repository(
        slug="github",
        name="GitHub (code repository)",
        domain="general",
        identifier_format=r"^[\w.-]+/[\w.-]+$",
        url_template="https://github.com/{id}",
        citation_template=(
            "Code is available at https://github.com/{id} (archived at "
            "Zenodo: https://doi.org/<assigned-doi>)."
        ),
    ),
}


# ---------------------------------------------------------------------------
# FAIR checklist


FAIRPrinciple = Literal["findable", "accessible", "interoperable", "reusable"]


@dataclass(frozen=True)
class FAIRItem:
    """One FAIR checklist item."""

    id: str
    principle: FAIRPrinciple
    rule: str


FAIR_CHECKLIST: list[FAIRItem] = [
    # Findable (4)
    FAIRItem(
        "F1",
        "findable",
        "Each dataset has a globally unique, persistent identifier (DOI / accession).",
    ),
    FAIRItem(
        "F2", "findable", "Each dataset has rich metadata (creator, title, repository, year)."
    ),
    FAIRItem("F3", "findable", "Metadata explicitly cites the identifier."),
    FAIRItem(
        "F4",
        "findable",
        "Dataset is indexed in a searchable resource (PubMed / Google Dataset Search).",
    ),
    # Accessible (3)
    FAIRItem(
        "A1", "accessible", "Identifier resolves to data via a standard protocol (HTTPS / FTP)."
    ),
    FAIRItem(
        "A2",
        "accessible",
        "Access protocol is open, free, and universally implementable, or restriction is explained.",
    ),
    FAIRItem("A3", "accessible", "Metadata remains accessible even when data is restricted."),
    # Interoperable (3)
    FAIRItem(
        "I1",
        "interoperable",
        "Data uses a formal, accessible, shared, broadly applicable representation.",
    ),
    FAIRItem(
        "I2", "interoperable", "Vocabularies follow FAIR principles (controlled vocab, ontology)."
    ),
    FAIRItem("I3", "interoperable", "Dataset includes qualified references to other (meta)data."),
    # Reusable (4)
    FAIRItem("R1", "reusable", "Released with a clear, accessible data usage license."),
    FAIRItem("R2", "reusable", "Associated with detailed provenance (how generated, by whom)."),
    FAIRItem(
        "R3",
        "reusable",
        "Meets domain-relevant community standards (data dictionary, file format).",
    ),
    FAIRItem("R4", "reusable", "README / data dictionary present and discoverable."),
]


# ---------------------------------------------------------------------------
# DAS scenarios + templates


class DAScenario(str, Enum):
    """The six common Data Availability scenarios."""

    PUBLIC_DEPOSIT = "public_deposit"
    RESTRICTED_HUMAN = "restricted_human"
    ON_REQUEST = "on_request"
    SUPPLEMENTARY_ONLY = "supplementary_only"
    INTERNAL_ONLY = "internal_only"
    CODE_ARCHIVED = "code_archived"


_SCENARIO_TEMPLATES: dict[DAScenario, str] = {
    DAScenario.PUBLIC_DEPOSIT: (
        "All datasets generated and analyzed in this study are publicly available. "
        "{repository_clauses} Source data underlying the main figures are provided "
        "in the Source Data file."
    ),
    DAScenario.RESTRICTED_HUMAN: (
        "Human {data_type} are controlled-access due to participant consent and ethics-board restrictions. "
        "Data are available under managed access at {repository_clause}. The Data Access "
        "Committee ({dac_contact}) will review applications within 4 weeks. "
        "Researchers must agree to a Data Use Agreement consistent with the original consent."
    ),
    DAScenario.ON_REQUEST: (
        "The datasets supporting the findings of this study are available from the corresponding "
        "author ({contact}) on reasonable request. Materials sharing follows the institution's "
        "Material Transfer Agreement; reuse for any purpose consistent with the original "
        "ethics approval will be granted within 8 weeks."
    ),
    DAScenario.SUPPLEMENTARY_ONLY: (
        "All data necessary to reproduce the analyses are provided in the Supplementary "
        "Information and Source Data files."
    ),
    DAScenario.INTERNAL_ONLY: (
        "⚠ AUTHOR INPUT NEEDED — this dataset is currently flagged as not-deposited. "
        "Nature-family journals will not accept this without a justification. Options:\n"
        "  (a) Deposit in a public repository before submission.\n"
        "  (b) Move to controlled-access (EGA / dbGaP) with a Data Access Committee.\n"
        "  (c) Request an editorial exception with a strong rationale."
    ),
    DAScenario.CODE_ARCHIVED: (
        "All analysis code is open-source and available at https://github.com/{github_repo}, "
        "with a frozen release archived at Zenodo (https://doi.org/{zenodo_doi})."
    ),
}


def statement_template(scenario: DAScenario | str) -> str:
    """Fetch a DAS template by scenario."""
    if isinstance(scenario, str):
        scenario = DAScenario(scenario)
    return _SCENARIO_TEMPLATES[scenario]


# ---------------------------------------------------------------------------
# Audit


@dataclass
class StatementAuditFinding:
    """One audit finding."""

    severity: Literal["blocker", "major", "minor"]
    message: str


def audit_statement(text: str) -> list[StatementAuditFinding]:
    """Run heuristic audits on a candidate DAS. Returns a list of findings."""
    findings: list[StatementAuditFinding] = []
    lowered = text.lower()

    # Blocker: vague "available on reasonable request" with no contact / DAC info.
    if "reasonable request" in lowered and "contact" not in lowered and "@" not in lowered:
        findings.append(
            StatementAuditFinding(
                "blocker",
                'DAS says "available on reasonable request" but no contact route is given. '
                "Specify a corresponding-author email or Data Access Committee.",
            )
        )

    # Blocker: human data without restriction clause
    if any(
        kw in lowered
        for kw in ("human participants", "patient cohort", "clinical data", "germline sequenc")
    ) and not any(
        kw in lowered for kw in ("controlled-access", "ega", "dbgap", "consent", "ethics")
    ):
        findings.append(
            StatementAuditFinding(
                "major",
                "Human data with no restriction clause. Nature requires explicit consent + "
                "controlled-access or anonymization details.",
            )
        )

    # Major: no accession identifiers mentioned at all
    if not any(
        kw in text for kw in ("GSE", "PRJ", "PXD", "PDB", "EMPIAR", "10.", "https://", "github.com")
    ):
        findings.append(
            StatementAuditFinding(
                "major",
                "No persistent identifier or URL detected in the DAS. Every dataset must "
                "resolve to a citable accession or DOI.",
            )
        )

    # Minor: "all data are available" without specifying where
    if "all data are available" in lowered and not any(
        kw in lowered for kw in ("supplementary", "source data", "repository", "deposited")
    ):
        findings.append(
            StatementAuditFinding(
                "minor",
                'Sentence "all data are available" is unfalsifiable without a destination. '
                "Name the supplementary file or repository.",
            )
        )

    return findings


__all__ = [
    "DAScenario",
    "FAIR_CHECKLIST",
    "FAIRItem",
    "FAIRPrinciple",
    "REPOSITORIES",
    "Repository",
    "StatementAuditFinding",
    "audit_statement",
    "statement_template",
]
