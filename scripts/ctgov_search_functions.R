# ============================================
# CT.gov Search Functions - R Package
# TruthCert TC-TRIALREG Enhanced
# Version: 1.0.0
# ============================================

#' @title CT.gov Search Functions
#' @description Evidence-based search functions for ClinicalTrials.gov API v2
#' @details Implements 10 validated search strategies with TruthCert verification

library(httr2)
library(jsonlite)
library(dplyr)
library(purrr)

# ============================================
# Configuration
# ============================================

CTGOV_API_BASE <- "https://clinicaltrials.gov/api/v2/studies"

# Condition synonyms database (empirically validated)
CONDITION_SYNONYMS <- list(
  "diabetes" = c("diabetes mellitus", "diabetic", "type 2 diabetes", "type 1 diabetes", "t2dm", "t1dm"),
  "hypertension" = c("high blood pressure", "elevated blood pressure", "htn"),
  "depression" = c("major depressive disorder", "mdd", "depressive disorder", "clinical depression"),
  "heart failure" = c("cardiac failure", "chf", "congestive heart failure", "hf"),
  "stroke" = c("cerebrovascular accident", "cva", "brain infarction", "ischemic stroke"),
  "breast cancer" = c("breast neoplasm", "breast carcinoma", "mammary cancer"),
  "asthma" = c("bronchial asthma", "asthmatic", "reactive airway disease"),
  "copd" = c("chronic obstructive pulmonary disease", "emphysema", "chronic bronchitis"),
  "alzheimer" = c("alzheimer disease", "alzheimer's disease", "ad", "dementia"),
  "parkinson" = c("parkinson disease", "parkinson's disease", "pd", "parkinsonian"),
  "autism" = c("autism spectrum disorder", "asd", "autistic disorder"),
  "covid-19" = c("covid", "coronavirus", "sars-cov-2"),
  "cystic fibrosis" = c("cf", "mucoviscidosis"),
  "psoriasis" = c("plaque psoriasis"),
  "eczema" = c("atopic dermatitis")
)

# Strategy definitions with empirical recall data
STRATEGIES <- list(
  S1 = list(
    name = "Condition Only (Maximum Recall)",
    expected_recall = 98.7,
    build = function(cond) sprintf("query.cond=%s&countTotal=true&pageSize=100", URLencode(cond, reserved = TRUE))
  ),
  S2 = list(
    name = "Interventional Studies",
    expected_recall = 98.7,
    build = function(cond) sprintf("query.cond=%s&query.term=%s&countTotal=true&pageSize=100",
                                   URLencode(cond, reserved = TRUE),
                                   URLencode("AREA[StudyType]INTERVENTIONAL", reserved = TRUE))
  ),
  S3 = list(
    name = "Randomized Allocation Only",
    expected_recall = 98.7,
    build = function(cond) sprintf("query.cond=%s&query.term=%s&countTotal=true&pageSize=100",
                                   URLencode(cond, reserved = TRUE),
                                   URLencode("AREA[DesignAllocation]RANDOMIZED", reserved = TRUE))
  ),
  S4 = list(
    name = "Phase 3/4 Studies",
    expected_recall = 45.5,
    build = function(cond) sprintf("query.cond=%s&query.term=%s&countTotal=true&pageSize=100",
                                   URLencode(cond, reserved = TRUE),
                                   URLencode("AREA[Phase](PHASE3 OR PHASE4)", reserved = TRUE))
  ),
  S5 = list(
    name = "Has Posted Results",
    expected_recall = 63.6,
    build = function(cond) sprintf("query.cond=%s&query.term=%s&countTotal=true&pageSize=100",
                                   URLencode(cond, reserved = TRUE),
                                   URLencode("AREA[ResultsFirstPostDate]RANGE[MIN,MAX]", reserved = TRUE))
  ),
  S6 = list(
    name = "Completed Status",
    expected_recall = 87.0,
    build = function(cond) sprintf("query.cond=%s&filter.overallStatus=COMPLETED&countTotal=true&pageSize=100",
                                   URLencode(cond, reserved = TRUE))
  ),
  S7 = list(
    name = "Interventional + Completed",
    expected_recall = 87.0,
    build = function(cond) sprintf("query.cond=%s&query.term=%s&filter.overallStatus=COMPLETED&countTotal=true&pageSize=100",
                                   URLencode(cond, reserved = TRUE),
                                   URLencode("AREA[StudyType]INTERVENTIONAL", reserved = TRUE))
  ),
  S8 = list(
    name = "RCT + Phase 3/4 + Completed",
    expected_recall = 42.9,
    build = function(cond) sprintf("query.cond=%s&query.term=%s&filter.overallStatus=COMPLETED&countTotal=true&pageSize=100",
                                   URLencode(cond, reserved = TRUE),
                                   URLencode("AREA[DesignAllocation]RANDOMIZED AND AREA[Phase](PHASE3 OR PHASE4)", reserved = TRUE))
  ),
  S9 = list(
    name = "Full-Text RCT Keywords",
    expected_recall = 79.2,
    build = function(cond) sprintf("query.term=%s&countTotal=true&pageSize=100",
                                   URLencode(paste(cond, "AND randomized AND controlled"), reserved = TRUE))
  ),
  S10 = list(
    name = "Treatment RCTs Only",
    expected_recall = 89.6,
    build = function(cond) sprintf("query.cond=%s&query.term=%s&countTotal=true&pageSize=100",
                                   URLencode(cond, reserved = TRUE),
                                   URLencode("AREA[DesignAllocation]RANDOMIZED AND AREA[DesignPrimaryPurpose]TREATMENT", reserved = TRUE))
  )
)

# ============================================
# Core Search Functions
# ============================================

#' Search ClinicalTrials.gov API
#'
#' @param query_string The query string to append to the API URL
#' @param max_results Maximum number of results to return (default: 100)
#' @param retry_count Number of retries on failure (default: 3)
#' @return List with totalCount, studies, time_sec, and url
#' @export
search_ctgov <- function(query_string, max_results = 100, retry_count = 3) {
  url <- paste0(CTGOV_API_BASE, "?", query_string)

  start_time <- Sys.time()

  for (attempt in 1:retry_count) {
    tryCatch({
      response <- request(url) |>
        req_timeout(30) |>
        req_retry(max_tries = 1) |>
        req_perform()

      data <- resp_body_json(response)
      time_sec <- as.numeric(difftime(Sys.time(), start_time, units = "secs"))

      return(list(
        success = TRUE,
        totalCount = data$totalCount %||% 0,
        studies = data$studies %||% list(),
        time_sec = round(time_sec, 2),
        url = url,
        timestamp = Sys.time()
      ))
    }, error = function(e) {
      if (attempt == retry_count) {
        return(list(
          success = FALSE,
          totalCount = 0,
          studies = list(),
          time_sec = 0,
          url = url,
          error = e$message,
          timestamp = Sys.time()
        ))
      }
      Sys.sleep(2^attempt)  # Exponential backoff
    })
  }
}

#' Run a specific search strategy
#'
#' @param condition The medical condition to search
#' @param strategy_id The strategy ID (S1-S10)
#' @return List with strategy results and metadata
#' @export
run_strategy <- function(condition, strategy_id) {
  if (!strategy_id %in% names(STRATEGIES)) {
    stop(paste("Invalid strategy ID:", strategy_id, ". Valid options: S1-S10"))
  }

  strategy <- STRATEGIES[[strategy_id]]
  query_string <- strategy$build(condition)

  result <- search_ctgov(query_string)

  return(list(
    strategy_id = strategy_id,
    strategy_name = strategy$name,
    expected_recall = strategy$expected_recall,
    condition = condition,
    totalCount = result$totalCount,
    time_sec = result$time_sec,
    url = result$url,
    success = result$success,
    timestamp = result$timestamp
  ))
}

#' Run all 10 search strategies for a condition
#'
#' @param condition The medical condition to search
#' @param strategies Vector of strategy IDs to run (default: all)
#' @return Data frame with all strategy results
#' @export
run_all_strategies <- function(condition, strategies = names(STRATEGIES)) {
  message(sprintf("Running %d strategies for condition: %s", length(strategies), condition))

  results <- map_dfr(strategies, function(sid) {
    message(sprintf("  Running %s...", sid))
    res <- run_strategy(condition, sid)
    as.data.frame(res)
  })

  # Calculate reduction from baseline (S1)
  baseline <- results$totalCount[results$strategy_id == "S1"]
  if (length(baseline) > 0 && baseline > 0) {
    results$reduction_pct <- round((1 - results$totalCount / baseline) * 100, 1)
  } else {
    results$reduction_pct <- 0
  }

  return(results)
}

# ============================================
# NCT ID Validation Functions
# ============================================

#' Validate a single NCT ID
#'
#' @param nct_id The NCT ID to validate (e.g., "NCT00000001")
#' @return List with validation result and study details
#' @export
validate_nct_id <- function(nct_id) {
  if (!grepl("^NCT\\d+$", nct_id, ignore.case = TRUE)) {
    return(list(
      nct_id = nct_id,
      valid = FALSE,
      error = "Invalid NCT ID format"
    ))
  }

  url <- sprintf("%s?query.id=%s&pageSize=1", CTGOV_API_BASE, nct_id)

  tryCatch({
    response <- request(url) |>
      req_timeout(15) |>
      req_perform()

    data <- resp_body_json(response)

    if (length(data$studies) > 0) {
      study <- data$studies[[1]]
      return(list(
        nct_id = nct_id,
        valid = TRUE,
        title = study$protocolSection$identificationModule$briefTitle %||% NA,
        status = study$protocolSection$statusModule$overallStatus %||% NA,
        phase = paste(study$protocolSection$designModule$phases %||% "N/A", collapse = ", "),
        study_type = study$protocolSection$designModule$studyType %||% NA
      ))
    } else {
      return(list(
        nct_id = nct_id,
        valid = FALSE,
        error = "NCT ID not found"
      ))
    }
  }, error = function(e) {
    return(list(
      nct_id = nct_id,
      valid = FALSE,
      error = e$message
    ))
  })
}

#' Validate multiple NCT IDs
#'
#' @param nct_ids Vector of NCT IDs
#' @param progress Show progress (default: TRUE)
#' @return Data frame with validation results
#' @export
validate_nct_ids <- function(nct_ids, progress = TRUE) {
  if (progress) message(sprintf("Validating %d NCT IDs...", length(nct_ids)))

  results <- map_dfr(nct_ids, function(nct_id) {
    if (progress) message(sprintf("  Checking %s...", nct_id))
    res <- validate_nct_id(nct_id)
    as.data.frame(res)
  })

  if (progress) {
    valid_count <- sum(results$valid)
    message(sprintf("Validation complete: %d valid, %d invalid",
                    valid_count, nrow(results) - valid_count))
  }

  return(results)
}

# ============================================
# Recall Testing Functions
# ============================================

#' Test recall of a strategy against known NCT IDs
#'
#' @param condition The medical condition
#' @param nct_ids Vector of known NCT IDs
#' @param strategy_id Strategy to test (default: "S1")
#' @return List with recall metrics
#' @export
test_recall <- function(condition, nct_ids, strategy_id = "S1") {
  message(sprintf("Testing recall for %s with %d NCT IDs using %s",
                  condition, length(nct_ids), strategy_id))

  strategy <- STRATEGIES[[strategy_id]]
  base_query <- strategy$build(condition)

  found <- 0

  for (nct_id in nct_ids) {
    # Check if NCT ID is in the strategy results
    check_query <- paste0(base_query, "&query.id=", nct_id)
    result <- search_ctgov(check_query)

    if (result$totalCount > 0) {
      found <- found + 1
    }

    Sys.sleep(0.5)  # Rate limiting
  }

  recall <- found / length(nct_ids) * 100

  return(list(
    strategy_id = strategy_id,
    strategy_name = strategy$name,
    condition = condition,
    total_nct_ids = length(nct_ids),
    found = found,
    not_found = length(nct_ids) - found,
    recall_pct = round(recall, 1),
    expected_recall = strategy$expected_recall
  ))
}

#' Test recall across all strategies
#'
#' @param condition The medical condition
#' @param nct_ids Vector of known NCT IDs
#' @return Data frame with recall results for all strategies
#' @export
test_recall_all_strategies <- function(condition, nct_ids) {
  results <- map_dfr(names(STRATEGIES), function(sid) {
    message(sprintf("Testing %s...", sid))
    res <- test_recall(condition, nct_ids, sid)
    as.data.frame(res)
  })

  return(results)
}

# ============================================
# TruthCert TC-TRIALREG Functions
# ============================================

#' Create a TruthCert scope lock for a search
#'
#' @param condition The medical condition
#' @param synonyms Vector of synonyms (optional)
#' @return Scope lock object
#' @export
create_scope_lock <- function(condition, synonyms = NULL) {
  if (is.null(synonyms)) {
    synonyms <- CONDITION_SYNONYMS[[tolower(condition)]] %||% character(0)
  }

  list(
    condition = condition,
    synonyms = synonyms,
    source_type = "ClinicalTrials.gov",
    api_version = "v2",
    timestamp = Sys.time(),
    hash = digest::digest(list(condition, synonyms, Sys.time()), algo = "sha256")
  )
}

#' Run TruthCert multi-witness validation
#'
#' @param condition The medical condition
#' @param witness_strategies Vector of strategy IDs (minimum 3)
#' @return Validation result with status (SHIPPED/REJECTED)
#' @export
truthcert_validate <- function(condition, witness_strategies = c("S1", "S3", "S10")) {
  if (length(witness_strategies) < 3) {
    stop("TruthCert requires minimum 3 witnesses")
  }

  message("=== TruthCert TC-TRIALREG Validation ===")
  message(sprintf("Scope Lock: condition = '%s'", condition))
  message(sprintf("Witnesses: %s", paste(witness_strategies, collapse = ", ")))

  # Create scope lock
  scope_lock <- create_scope_lock(condition)

  # Run witnesses
  witness_results <- map(witness_strategies, function(sid) {
    message(sprintf("  Running witness %s...", sid))
    run_strategy(condition, sid)
  })

  # Check agreement (Gate B5)
  counts <- sapply(witness_results, function(x) x$totalCount)
  mean_count <- mean(counts)
  max_diff <- max(counts) - min(counts)
  agreement <- 1 - (max_diff / mean_count)

  message(sprintf("  Witness counts: %s", paste(counts, collapse = ", ")))
  message(sprintf("  Agreement: %.1f%%", agreement * 100))

  # Determine status
  if (agreement >= 0.80) {
    status <- "SHIPPED"
    message("  Gate B5: PASSED")
  } else {
    status <- "REJECTED"
    message("  Gate B5: FAILED")
  }

  message(sprintf("=== TruthCert Status: %s ===", status))

  return(list(
    status = status,
    scope_lock = scope_lock,
    witness_results = witness_results,
    agreement = round(agreement * 100, 1),
    gate_b5_passed = agreement >= 0.80,
    timestamp = Sys.time()
  ))
}

#' Create TruthCert audit log entry
#'
#' @param validation_result Result from truthcert_validate
#' @return Formatted ledger entry
#' @export
create_ledger_entry <- function(validation_result) {
  list(
    bundle_id = digest::digest(validation_result, algo = "sha256"),
    lane = "verification",
    policy_anchor = list(
      scope_lock_ref = validation_result$scope_lock$hash,
      validator_version = "validators-2026-01-v3",
      thresholds = list(fact_agreement = 0.80)
    ),
    gate_outcomes = list(
      B5_semantic_agreement = validation_result$gate_b5_passed
    ),
    terminal_state = validation_result$status,
    timestamp = validation_result$timestamp
  )
}

# ============================================
# Synonym Expansion Functions
# ============================================

#' Get synonyms for a condition
#'
#' @param condition The medical condition
#' @return Vector of synonyms
#' @export
get_synonyms <- function(condition) {
  synonyms <- CONDITION_SYNONYMS[[tolower(condition)]]
  if (is.null(synonyms)) {
    message(sprintf("No synonyms found for '%s'. Using condition only.", condition))
    return(condition)
  }
  return(c(condition, synonyms))
}

#' Build synonym-expanded search query
#'
#' @param condition The medical condition
#' @param strategy_id Strategy to use
#' @return Query string with synonym expansion
#' @export
build_synonym_query <- function(condition, strategy_id = "S3") {
  synonyms <- get_synonyms(condition)

  # Build OR query for condition field
  cond_query <- paste(sprintf('"%s"', synonyms), collapse = " OR ")

  strategy <- STRATEGIES[[strategy_id]]

  # Modify strategy to use expanded condition
  sprintf("query.cond=%s&query.term=%s&countTotal=true&pageSize=100",
          URLencode(paste0("(", cond_query, ")"), reserved = TRUE),
          URLencode("AREA[DesignAllocation]RANDOMIZED", reserved = TRUE))
}

# ============================================
# Reporting Functions
# ============================================

#' Generate strategy comparison report
#'
#' @param condition The medical condition
#' @param output_file Optional file path to save report
#' @return Report as a list
#' @export
generate_strategy_report <- function(condition, output_file = NULL) {
  message(sprintf("Generating strategy report for: %s", condition))

  # Run all strategies
  results <- run_all_strategies(condition)

  # Calculate metrics
  baseline <- results$totalCount[results$strategy_id == "S1"]

  report <- list(
    condition = condition,
    timestamp = Sys.time(),
    baseline_count = baseline,
    strategy_results = results,
    recommendations = list(
      max_sensitivity = "S1, S2, or S3 (98.7% recall)",
      balanced = "S10 (89.6% recall, 60% reduction)",
      focused = "S8 (42.9% recall, 90% reduction)"
    ),
    synonyms = get_synonyms(condition),
    registry_urls = list(
      ctgov = sprintf("https://clinicaltrials.gov/search?cond=%s", URLencode(condition)),
      ictrp = sprintf("https://trialsearch.who.int/Default.aspx?SearchAll=%s", URLencode(condition))
    )
  )

  if (!is.null(output_file)) {
    jsonlite::write_json(report, output_file, pretty = TRUE, auto_unbox = TRUE)
    message(sprintf("Report saved to: %s", output_file))
  }

  return(report)
}

#' Print strategy summary table
#'
#' @param results Data frame from run_all_strategies
#' @export
print_strategy_summary <- function(results) {
  cat("\n=== CT.gov Search Strategy Comparison ===\n\n")

  summary <- results %>%
    select(strategy_id, strategy_name, totalCount, expected_recall, reduction_pct, time_sec) %>%
    mutate(
      totalCount = format(totalCount, big.mark = ","),
      expected_recall = paste0(expected_recall, "%"),
      reduction_pct = paste0(reduction_pct, "%"),
      time_sec = paste0(time_sec, "s")
    )

  print(summary, row.names = FALSE)

  cat("\n=== Recommendations ===\n")
  cat("- Maximum sensitivity: Use S1, S2, or S3 (98.7% recall)\n")
  cat("- Balanced approach: Use S10 (89.6% recall, ~60% reduction)\n")
  cat("- Focused search: Use S8 (42.9% recall, ~90% reduction)\n")
  cat("- ALWAYS: Also search WHO ICTRP and document search date\n\n")
}

# ============================================
# Example Usage
# ============================================

if (FALSE) {
  # Run all strategies for diabetes
  results <- run_all_strategies("diabetes")
  print_strategy_summary(results)

  # Validate NCT IDs
  nct_ids <- c("NCT00000001", "NCT00400712", "NCT02717715")
  validation <- validate_nct_ids(nct_ids)

  # TruthCert validation
  tc_result <- truthcert_validate("diabetes")

  # Generate report
  report <- generate_strategy_report("diabetes", "diabetes_report.json")
}
