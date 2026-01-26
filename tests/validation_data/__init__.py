"""
Validation Data Package

Provides validated NCT ID datasets and AACT database integration
for systematic review search strategy testing and validation.

Usage:
    from tests.validation_data import (
        get_all_nct_ids,
        get_nct_ids_by_condition,
        get_validation_metadata,
        CONDITION_CATEGORIES,
    )
"""

from .expanded_nct_dataset import (
    # Classes
    ValidatedNCT,
    ValidationSource,
    StudyCharacteristic,

    # Constants
    CONDITION_CATEGORIES,
    ALL_CONDITION_DATASETS,

    # Functions
    get_all_nct_ids,
    get_nct_ids_by_condition,
    get_validated_ncts,
    get_validation_metadata,
    get_ncts_by_source,
    get_edge_case_ncts,
    export_to_json,
    export_nct_list,
)

from .aact_validator import (
    AACTValidator,
    ValidatedStudy,
    ValidationSummary,
    quick_validate,
    validate_expanded_dataset,
)

__all__ = [
    # Expanded dataset
    "ValidatedNCT",
    "ValidationSource",
    "StudyCharacteristic",
    "CONDITION_CATEGORIES",
    "ALL_CONDITION_DATASETS",
    "get_all_nct_ids",
    "get_nct_ids_by_condition",
    "get_validated_ncts",
    "get_validation_metadata",
    "get_ncts_by_source",
    "get_edge_case_ncts",
    "export_to_json",
    "export_nct_list",

    # AACT Validator
    "AACTValidator",
    "ValidatedStudy",
    "ValidationSummary",
    "quick_validate",
    "validate_expanded_dataset",
]
