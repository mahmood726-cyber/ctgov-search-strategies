#' CT.gov Search Strategy Functions for R
#'
#' @title ctgov.search: ClinicalTrials.gov Search Strategy Package
#' @description Comprehensive R interface for ClinicalTrials.gov API v2
#'   with 10 validated search strategies based on Cochrane guidance.
#'
#' @details
#' This package provides functions for:
#' \itemize{
#'   \item Searching ClinicalTrials.gov with 10 validated strategies
#'   \item Comparing search strategy performance
#'   \item Validating NCT IDs
#'   \item Calculating recall against known studies
#'   \item Synonym expansion for improved recall
#'   \item Batch searching and pagination
#' }
#'
#' @section Search Strategies:
#' \describe{
#'   \item{S1}{Condition Only (Maximum Recall) - Cochrane recommended}
#'   \item{S2}{Interventional Studies}
#'   \item{S3}{Randomized Allocation Only}
#'   \item{S4}{Phase 3/4 Studies}
#'   \item{S5}{Has Posted Results}
#'   \item{S6}{Completed Status}
#'   \item{S7}{Interventional + Completed}
#'   \item{S8}{RCT + Phase 3/4 + Completed}
#'   \item{S9}{Full-Text RCT Keywords}
#'   \item{S10}{Treatment RCTs Only}
#' }
#'
#' @author CT.gov Search Strategy Project
#' @references
#'   Cochrane Handbook for Systematic Reviews of Interventions
#'   ClinicalTrials.gov API v2 Documentation
#'
#' @import httr
#' @import jsonlite
#' @importFrom data.table data.table rbindlist setDT
#' @importFrom utils URLencode
#'
#' @name ctgov.search-package
#' @aliases ctgov.search
#' @docType package
NULL

# ==============================================================================
# Package Dependencies and Imports
# ==============================================================================

#' @noRd
.onLoad <- function(libname, pkgname) {
  # Check for required packages
  required_packages <- c("httr", "jsonlite")
  for (pkg in required_packages) {
    if (!requireNamespace(pkg, quietly = TRUE)) {
      warning(sprintf("Package '%s' is required but not installed.", pkg))
    }
  }

  # Try to load data.table, fall back to base R if not available
  if (!requireNamespace("data.table", quietly = TRUE)) {
    message("data.table not available, using base R data.frames")
  }
}

# Load packages (suppress messages in non-interactive sessions)
suppressPackageStartupMessages({
  library(httr)
  library(jsonlite)
  if (requireNamespace("data.table", quietly = TRUE)) {
    library(data.table)
  }
})

# ==============================================================================
# API Configuration Constants
# ==============================================================================

#' CT.gov API Base URL
#' @noRd
CTGOV_API <- "https://clinicaltrials.gov/api/v2/studies"

#' Default timeout for HTTP requests (seconds)
#' @noRd
DEFAULT_TIMEOUT <- 30

#' Default page size for paginated requests
#' @noRd
DEFAULT_PAGE_SIZE <- 1000

#' Rate limit delay between requests (seconds)
#' @noRd
RATE_LIMIT_DELAY <- 0.3

#' User agent for HTTP requests
#' @noRd
USER_AGENT <- "CTgov-Search-R-Package/2.1"

#' Maximum retry attempts for failed requests
#' @noRd
MAX_RETRIES <- 3

#' Backoff factor for retry delays (seconds)
#' @noRd
RETRY_BACKOFF <- 0.5

#' HTTP status codes that should trigger retry
#' @noRd
RETRY_STATUS_CODES <- c(429, 500, 502, 503, 504)

# ==============================================================================
# Null Coalescing Operator
# ==============================================================================

#' Null coalescing operator
#' @param a First value
#' @param b Default value if a is NULL/NA/empty
#' @return a if not null/empty, otherwise b
#' @noRd
`%||%` <- function(a, b) {
  if (is.null(a) || length(a) == 0 || (length(a) == 1 && is.na(a))) b else a
}

# ==============================================================================
# Search Strategies Definition
# ==============================================================================

#' Search Strategies
#'
#' @description A list of 10 validated search strategies for ClinicalTrials.gov
#'
#' @format A named list with strategy configurations:
#' \describe{
#'   \item{name}{Display name of the strategy}
#'   \item{desc}{Description of what the strategy filters}
#'   \item{retention}{Expected percentage of S1 baseline results}
#'   \item{sensitivity}{Sensitivity level (high/medium/low)}
#'   \item{build_query}{Function to build the query URL parameters}
#' }
#'
#' @export
#' @examples
#' # View strategy names
#' names(STRATEGIES)
#'
#' # Get S1 description
#' STRATEGIES$S1$desc
STRATEGIES <- list(
  S1 = list(
    name = "Condition Only (Maximum Recall)",
    desc = "Cochrane recommended - no filters for maximum sensitivity",
    retention = 100,
    sensitivity = "high",
    build_query = function(cond, intr = NULL) {
      paste0("query.cond=", URLencode(cond, reserved = TRUE))
    }
  ),
  S2 = list(
    name = "Interventional Studies",
    desc = "All interventional study types",
    retention = 77,
    sensitivity = "high",
    build_query = function(cond, intr = NULL) {
      paste0("query.cond=", URLencode(cond, reserved = TRUE),
             "&query.term=", URLencode("AREA[StudyType]INTERVENTIONAL", reserved = TRUE))
    }
  ),
  S3 = list(
    name = "Randomized Allocation Only",
    desc = "True RCTs - excludes single-arm trials",
    retention = 54,
    sensitivity = "medium",
    build_query = function(cond, intr = NULL) {
      paste0("query.cond=", URLencode(cond, reserved = TRUE),
             "&query.term=", URLencode("AREA[DesignAllocation]RANDOMIZED", reserved = TRUE))
    }
  ),
  S4 = list(
    name = "Phase 3/4 Studies",
    desc = "Later phase trials only",
    retention = 16,
    sensitivity = "low",
    build_query = function(cond, intr = NULL) {
      paste0("query.cond=", URLencode(cond, reserved = TRUE),
             "&query.term=", URLencode("AREA[Phase](PHASE3 OR PHASE4)", reserved = TRUE))
    }
  ),
  S5 = list(
    name = "Has Posted Results",
    desc = "Studies with results posted on CT.gov",
    retention = 14,
    sensitivity = "low",
    build_query = function(cond, intr = NULL) {
      paste0("query.cond=", URLencode(cond, reserved = TRUE),
             "&query.term=", URLencode("AREA[ResultsFirstPostDate]RANGE[MIN,MAX]", reserved = TRUE))
    }
  ),
  S6 = list(
    name = "Completed Status",
    desc = "Completed trials only",
    retention = 55,
    sensitivity = "medium",
    build_query = function(cond, intr = NULL) {
      paste0("query.cond=", URLencode(cond, reserved = TRUE),
             "&filter.overallStatus=COMPLETED")
    }
  ),
  S7 = list(
    name = "Interventional + Completed",
    desc = "Completed interventional studies",
    retention = 43,
    sensitivity = "medium",
    build_query = function(cond, intr = NULL) {
      paste0("query.cond=", URLencode(cond, reserved = TRUE),
             "&query.term=", URLencode("AREA[StudyType]INTERVENTIONAL", reserved = TRUE),
             "&filter.overallStatus=COMPLETED")
    }
  ),
  S8 = list(
    name = "RCT + Phase 3/4 + Completed",
    desc = "Highest quality subset - completed Phase 3/4 RCTs",
    retention = 8,
    sensitivity = "low",
    build_query = function(cond, intr = NULL) {
      paste0("query.cond=", URLencode(cond, reserved = TRUE),
             "&query.term=", URLencode("AREA[DesignAllocation]RANDOMIZED AND AREA[Phase](PHASE3 OR PHASE4)", reserved = TRUE),
             "&filter.overallStatus=COMPLETED")
    }
  ),
  S9 = list(
    name = "Full-Text RCT Keywords",
    desc = "Text search: condition AND randomized AND controlled",
    retention = 72,
    sensitivity = "medium",
    build_query = function(cond, intr = NULL) {
      paste0("query.term=", URLencode(paste(cond, "AND randomized AND controlled"), reserved = TRUE))
    }
  ),
  S10 = list(
    name = "Treatment RCTs Only",
    desc = "Randomized + Treatment purpose",
    retention = 36,
    sensitivity = "medium",
    build_query = function(cond, intr = NULL) {
      paste0("query.cond=", URLencode(cond, reserved = TRUE),
             "&query.term=", URLencode("AREA[DesignAllocation]RANDOMIZED AND AREA[DesignPrimaryPurpose]TREATMENT", reserved = TRUE))
    }
  )
)

# ==============================================================================
# MeSH Synonyms for Common Conditions
# ==============================================================================

#' MeSH Synonym Dictionary
#'
#' @description Common medical conditions and their MeSH synonyms for query expansion
#'
#' @format A named list where keys are conditions and values are vectors of synonyms
#'
#' @export
#' @examples
#' # Get synonyms for diabetes
#' SYNONYMS[["diabetes"]]
SYNONYMS <- list(

diabetes = c("diabetes mellitus", "diabetic", "type 2 diabetes", "type 1 diabetes",
               "T2DM", "T1DM", "NIDDM", "IDDM"),
  hypertension = c("high blood pressure", "elevated blood pressure", "HTN",
                   "arterial hypertension", "essential hypertension"),
  depression = c("major depressive disorder", "MDD", "depressive disorder",
                 "unipolar depression", "clinical depression"),
  `heart failure` = c("cardiac failure", "CHF", "congestive heart failure",
                      "HF", "cardiac decompensation"),
  stroke = c("cerebrovascular accident", "CVA", "brain infarction",
             "cerebral infarction", "ischemic stroke", "hemorrhagic stroke"),
  `breast cancer` = c("breast neoplasm", "breast carcinoma", "mammary cancer",
                      "breast malignancy", "breast tumor"),
  asthma = c("bronchial asthma", "asthmatic", "reactive airway disease"),
  `lung cancer` = c("pulmonary carcinoma", "lung neoplasm", "NSCLC", "SCLC",
                    "non-small cell lung cancer", "small cell lung cancer"),
  `prostate cancer` = c("prostate carcinoma", "prostatic neoplasm", "prostate malignancy"),
  covid = c("COVID-19", "SARS-CoV-2", "coronavirus disease 2019", "coronavirus")
)

# ==============================================================================
# Helper Functions
# ==============================================================================

#' Build Query URL
#'
#' @description Constructs the full API URL from condition and strategy
#'
#' @param condition Character string of the medical condition
#' @param strategy Strategy ID (S1-S10)
#' @param page_size Number of results to request
#' @param count_total Whether to include total count
#' @param page_token Optional pagination token for subsequent pages
#'
#' @return Complete URL string for API request
#'
#' @export
#' @examples
#' url <- build_query_url("diabetes", "S1")
#' url <- build_query_url("breast cancer", "S3", page_size = 100)
build_query_url <- function(condition, strategy = "S1", page_size = 1,
                            count_total = TRUE, page_token = NULL) {
  if (!strategy %in% names(STRATEGIES)) {
    stop(paste("Unknown strategy:", strategy, ". Valid:", paste(names(STRATEGIES), collapse = ", ")))
  }

  strat <- STRATEGIES[[strategy]]
  query <- strat$build_query(condition, NULL)

  url <- paste0(CTGOV_API, "?", query)

  if (count_total) {
    url <- paste0(url, "&countTotal=true")
  }

  url <- paste0(url, "&pageSize=", min(page_size, DEFAULT_PAGE_SIZE))

  if (!is.null(page_token)) {
    url <- paste0(url, "&pageToken=", URLencode(page_token, reserved = TRUE))
  }

  return(url)
}

#' Parse CT.gov API Response
#'
#' @description Parses JSON response from CT.gov API
#'
#' @param response httr response object
#'
#' @return List with parsed data or error information
#'
#' @export
#' @examples
#' \dontrun{
#' resp <- httr::GET("https://clinicaltrials.gov/api/v2/studies?query.cond=diabetes&pageSize=1")
#' data <- parse_ctgov_response(resp)
#' }
parse_ctgov_response <- function(response) {
  if (status_code(response) != 200) {
    return(list(
      success = FALSE,
      error = paste("HTTP", status_code(response)),
      total_count = NA,
      studies = NULL,
      next_page_token = NULL
    ))
  }

  tryCatch({
    data <- fromJSON(content(response, "text", encoding = "UTF-8"), flatten = TRUE)

    list(
      success = TRUE,
      error = NULL,
      total_count = data$totalCount %||% 0,
      studies = data$studies,
      next_page_token = data$nextPageToken %||% NULL
    )
  }, error = function(e) {
    list(
      success = FALSE,
      error = paste("JSON parse error:", e$message),
      total_count = NA,
      studies = NULL,
      next_page_token = NULL
    )
  })
}

#' Extract NCT IDs from Studies
#'
#' @description Extracts unique NCT IDs from CT.gov API study records
#'
#' @param studies Data frame or list of study records from CT.gov API
#'
#' @return Character vector of unique NCT IDs (uppercase)
#'
#' @export
#' @examples
#' \dontrun{
#' result <- ctgov_search("diabetes", return_studies = TRUE)
#' nct_ids <- extract_nct_ids(result$studies)
#' }
extract_nct_ids <- function(studies) {
  if (is.null(studies) || length(studies) == 0) {
    return(character(0))
  }

  nct_ids <- tryCatch({
    if (is.data.frame(studies)) {
      # API v2 nested structure
      if ("protocolSection.identificationModule.nctId" %in% names(studies)) {
        studies$protocolSection.identificationModule.nctId
      } else if ("nctId" %in% names(studies)) {
        studies$nctId
      } else {
        character(0)
      }
    } else if (is.list(studies)) {
      sapply(studies, function(s) {
        s$protocolSection$identificationModule$nctId %||%
          s$nctId %||%
          NA_character_
      })
    } else {
      character(0)
    }
  }, error = function(e) character(0))

  unique(toupper(na.omit(nct_ids)))
}

#' HTTP Request with Retry Logic
#'
#' @description Makes HTTP GET request with automatic retry on failure
#'
#' @param url Full URL for the request
#' @param timeout Request timeout in seconds
#' @param max_retries Maximum number of retry attempts
#' @param backoff_factor Multiplier for retry delay
#'
#' @return httr response object
#'
#' @noRd
http_get_with_retry <- function(url, timeout = DEFAULT_TIMEOUT,
                                max_retries = MAX_RETRIES,
                                backoff_factor = RETRY_BACKOFF) {
  for (attempt in 1:(max_retries + 1)) {
    response <- tryCatch({
      GET(url,
          timeout(timeout),
          user_agent(USER_AGENT),
          add_headers(Accept = "application/json"))
    }, error = function(e) {
      if (attempt <= max_retries) {
        Sys.sleep(backoff_factor * (2 ^ (attempt - 1)))
        return(NULL)
      }
      stop(e)
    })

    if (!is.null(response)) {
      status <- status_code(response)

      # Success
      if (status == 200) {
        return(response)
      }

      # Retryable error
      if (status %in% RETRY_STATUS_CODES && attempt <= max_retries) {
        Sys.sleep(backoff_factor * (2 ^ (attempt - 1)))
        next
      }

      # Non-retryable error or max retries reached
      return(response)
    }
  }

  stop("Max retries exceeded")
}

#' Validate NCT ID Format
#'
#' @description Checks if a string is a valid NCT ID format (NCT followed by 8 digits)
#'
#' @param nct_id String to validate
#'
#' @return Logical TRUE if valid format, FALSE otherwise
#'
#' @export
#' @examples
#' is_valid_nct("NCT00000001")  # TRUE
#' is_valid_nct("nct12345678")  # TRUE (case insensitive)
#' is_valid_nct("NCT123")       # FALSE (too short)
#' is_valid_nct("XYZ12345678")  # FALSE (wrong prefix)
is_valid_nct <- function(nct_id) {
  if (is.null(nct_id) || is.na(nct_id) || nchar(nct_id) == 0) {
    return(FALSE)
  }
  grepl("^NCT\\d{8}$", toupper(trimws(nct_id)))
}

#' Normalize NCT IDs
#'
#' @description Normalizes a vector of NCT IDs to uppercase, trimmed format
#'
#' @param nct_ids Character vector of NCT IDs
#'
#' @return List with valid_ids and invalid_ids vectors
#'
#' @noRd
normalize_nct_ids <- function(nct_ids) {
  if (is.null(nct_ids) || length(nct_ids) == 0) {
    return(list(valid_ids = character(0), invalid_ids = character(0)))
  }

  cleaned <- toupper(trimws(nct_ids))
  valid_mask <- sapply(cleaned, is_valid_nct)

  list(
    valid_ids = unique(cleaned[valid_mask]),
    invalid_ids = unique(cleaned[!valid_mask])
  )
}

# ==============================================================================
# Core Search Functions
# ==============================================================================

#' Search ClinicalTrials.gov
#'
#' @description Execute a search using specified strategy
#'
#' @param condition Character string of the medical condition to search
#' @param strategy Strategy ID (S1-S10). Default is S1 (maximum recall).
#' @param intervention Optional intervention filter
#' @param max_results Maximum number of results to return. Default is 1000.
#' @param return_studies Logical. Whether to return full study details. Default FALSE.
#' @param timeout Request timeout in seconds. Default 30.
#'
#' @return List with:
#' \describe{
#'   \item{strategy_id}{Strategy used}
#'   \item{strategy_name}{Name of the strategy}
#'   \item{condition}{Condition searched}
#'   \item{total_count}{Total number of matching studies}
#'   \item{studies}{Study data if return_studies=TRUE}
#'   \item{nct_ids}{Vector of NCT IDs if return_studies=TRUE}
#'   \item{url}{Query URL used}
#'   \item{execution_time}{Time taken in seconds}
#'   \item{error}{Error message if any}
#' }
#'
#' @export
#' @examples
#' \dontrun{
#' # Basic search
#' result <- ctgov_search("diabetes")
#' print(result$total_count)
#'
#' # Search for RCTs only
#' rct_result <- ctgov_search("diabetes", strategy = "S3")
#'
#' # Get study details
#' detailed <- ctgov_search("diabetes", strategy = "S1",
#'                          max_results = 100, return_studies = TRUE)
#' }
ctgov_search <- function(condition, strategy = "S1", intervention = NULL,
                         max_results = 1000, return_studies = FALSE,
                         timeout = DEFAULT_TIMEOUT) {

  # Validate strategy
  if (!strategy %in% names(STRATEGIES)) {
    stop(paste("Unknown strategy:", strategy,
               ". Valid strategies:", paste(names(STRATEGIES), collapse = ", ")))
  }

  strat <- STRATEGIES[[strategy]]

  # Build the query
  query <- strat$build_query(condition, intervention)

  # Determine page size
  page_size <- if (return_studies) min(max_results, DEFAULT_PAGE_SIZE) else 1

  url <- paste0(CTGOV_API, "?", query, "&countTotal=true&pageSize=", page_size)

  start_time <- Sys.time()

  result <- tryCatch({
    response <- http_get_with_retry(url, timeout = timeout)
    parsed <- parse_ctgov_response(response)

    if (!parsed$success) {
      return(list(
        strategy_id = strategy,
        strategy_name = strat$name,
        condition = condition,
        total_count = NA,
        studies = NULL,
        nct_ids = character(0),
        url = url,
        execution_time = as.numeric(difftime(Sys.time(), start_time, units = "secs")),
        error = parsed$error
      ))
    }

    # If return_studies and need more pages, paginate
    all_studies <- parsed$studies
    next_token <- parsed$next_page_token

    if (return_studies && !is.null(next_token) &&
        !is.null(all_studies) && nrow(all_studies) < max_results) {

      while (!is.null(next_token) &&
             (is.null(all_studies) || nrow(all_studies) < max_results)) {

        Sys.sleep(RATE_LIMIT_DELAY)

        page_url <- paste0(CTGOV_API, "?", query,
                           "&pageSize=", page_size,
                           "&pageToken=", URLencode(next_token, reserved = TRUE))

        page_response <- http_get_with_retry(page_url, timeout = timeout)
        page_parsed <- parse_ctgov_response(page_response)

        if (!page_parsed$success || is.null(page_parsed$studies)) {
          break
        }

        all_studies <- rbind(all_studies, page_parsed$studies)
        next_token <- page_parsed$next_page_token
      }
    }

    # Extract NCT IDs
    nct_ids <- if (return_studies && !is.null(all_studies)) {
      extract_nct_ids(all_studies)
    } else {
      character(0)
    }

    list(
      strategy_id = strategy,
      strategy_name = strat$name,
      condition = condition,
      total_count = parsed$total_count,
      studies = if (return_studies) all_studies else NULL,
      nct_ids = nct_ids,
      url = url,
      execution_time = as.numeric(difftime(Sys.time(), start_time, units = "secs")),
      error = NULL
    )

  }, error = function(e) {
    list(
      strategy_id = strategy,
      strategy_name = strat$name,
      condition = condition,
      total_count = NA,
      studies = NULL,
      nct_ids = character(0),
      url = url,
      execution_time = as.numeric(difftime(Sys.time(), start_time, units = "secs")),
      error = e$message
    )
  })

  return(result)
}

#' Compare All Search Strategies
#'
#' @description Run all 10 strategies for a condition and compare results
#'
#' @param condition Condition to search
#' @param intervention Optional intervention filter
#' @param verbose Logical. Print progress messages. Default TRUE.
#'
#' @return Data frame with columns: strategy_id, strategy_name, condition,
#'         total_count, pct_baseline, execution_time, url, error
#'
#' @export
#' @examples
#' \dontrun{
#' results <- ctgov_compare_strategies("diabetes")
#' print(results)
#'
#' # Without progress messages
#' results <- ctgov_compare_strategies("breast cancer", verbose = FALSE)
#' }
ctgov_compare_strategies <- function(condition, intervention = NULL, verbose = TRUE) {

  results <- list()

  for (strat_id in names(STRATEGIES)) {
    if (verbose) cat("Testing", strat_id, "-", STRATEGIES[[strat_id]]$name, "...\n")

    result <- ctgov_search(condition, strategy = strat_id, intervention = intervention)

    results[[strat_id]] <- data.frame(
      strategy_id = result$strategy_id,
      strategy_name = result$strategy_name,
      condition = result$condition,
      total_count = result$total_count %||% NA,
      execution_time = result$execution_time,
      url = result$url,
      error = result$error %||% "",
      stringsAsFactors = FALSE
    )

    Sys.sleep(RATE_LIMIT_DELAY)
  }

  df <- do.call(rbind, results)
  rownames(df) <- NULL

  # Calculate percentage of baseline (S1)
  baseline <- df$total_count[df$strategy_id == "S1"]
  if (!is.na(baseline) && baseline > 0) {
    df$pct_baseline <- round(df$total_count / baseline * 100, 1)
  } else {
    df$pct_baseline <- NA
  }

  # Reorder columns
  df <- df[, c("strategy_id", "strategy_name", "condition", "total_count",
               "pct_baseline", "execution_time", "url", "error")]

  # Convert to data.table if available
  if (requireNamespace("data.table", quietly = TRUE)) {
    df <- data.table::as.data.table(df)
  }

  return(df)
}

#' Validate NCT IDs
#'
#' @description Check if NCT IDs exist on ClinicalTrials.gov
#'
#' @param nct_ids Character vector of NCT IDs to validate
#' @param verbose Logical. Print progress messages. Default TRUE.
#'
#' @return Data frame with columns: nct_id, exists, error
#'
#' @export
#' @examples
#' \dontrun{
#' ids <- c("NCT03702452", "NCT00400712", "NCT99999999")
#' validation <- ctgov_validate_nct_ids(ids)
#' print(validation)
#' }
ctgov_validate_nct_ids <- function(nct_ids, verbose = TRUE) {

  if (is.null(nct_ids) || length(nct_ids) == 0) {
    return(data.frame(nct_id = character(0), exists = logical(0),
                      error = character(0), stringsAsFactors = FALSE))
  }

  # Normalize and validate format
  normalized <- normalize_nct_ids(nct_ids)

  results <- list()

  # Mark invalid format IDs
  for (invalid_id in normalized$invalid_ids) {
    results[[invalid_id]] <- data.frame(
      nct_id = invalid_id,
      exists = FALSE,
      error = "Invalid NCT ID format",
      stringsAsFactors = FALSE
    )
  }

  # Check valid format IDs against API
  valid_ids <- normalized$valid_ids

  if (length(valid_ids) > 0) {
    # Batch validate in groups of 50
    batch_size <- 50

    for (batch_start in seq(1, length(valid_ids), by = batch_size)) {
      batch_end <- min(batch_start + batch_size - 1, length(valid_ids))
      batch <- valid_ids[batch_start:batch_end]

      # Build OR query for batch
      id_query <- paste(batch, collapse = " OR ")
      url <- paste0(CTGOV_API, "?query.id=", URLencode(id_query, reserved = TRUE),
                    "&countTotal=true&pageSize=", length(batch))

      tryCatch({
        response <- http_get_with_retry(url)
        parsed <- parse_ctgov_response(response)

        if (parsed$success && !is.null(parsed$studies)) {
          found_ids <- extract_nct_ids(parsed$studies)

          for (nct_id in batch) {
            results[[nct_id]] <- data.frame(
              nct_id = nct_id,
              exists = nct_id %in% found_ids,
              error = NA_character_,
              stringsAsFactors = FALSE
            )
          }
        } else {
          # API error - check individually
          for (nct_id in batch) {
            single_url <- paste0(CTGOV_API, "/", nct_id)
            single_resp <- tryCatch({
              http_get_with_retry(single_url, timeout = 10)
            }, error = function(e) NULL)

            exists <- !is.null(single_resp) && status_code(single_resp) == 200
            results[[nct_id]] <- data.frame(
              nct_id = nct_id,
              exists = exists,
              error = if (exists) NA_character_ else "Not found",
              stringsAsFactors = FALSE
            )
            Sys.sleep(RATE_LIMIT_DELAY)
          }
        }
      }, error = function(e) {
        for (nct_id in batch) {
          results[[nct_id]] <- data.frame(
            nct_id = nct_id,
            exists = NA,
            error = e$message,
            stringsAsFactors = FALSE
          )
        }
      })

      if (verbose && batch_end < length(valid_ids)) {
        cat("Validated", batch_end, "/", length(valid_ids), "NCT IDs\n")
      }

      Sys.sleep(RATE_LIMIT_DELAY)
    }
  }

  df <- do.call(rbind, results)
  rownames(df) <- NULL

  if (requireNamespace("data.table", quietly = TRUE)) {
    df <- data.table::as.data.table(df)
  }

  return(df)
}

#' Get Study Details
#'
#' @description Retrieve full details for a specific study by NCT ID
#'
#' @param nct_id NCT ID of the study (e.g., "NCT00000001")
#'
#' @return List with study details, or NULL if not found
#'
#' @export
#' @examples
#' \dontrun{
#' study <- ctgov_get_study_details("NCT03702452")
#' if (!is.null(study)) {
#'   print(study$protocolSection$identificationModule$briefTitle)
#' }
#' }
ctgov_get_study_details <- function(nct_id) {

  if (!is_valid_nct(nct_id)) {
    warning("Invalid NCT ID format: ", nct_id)
    return(NULL)
  }

  nct_id <- toupper(trimws(nct_id))
  url <- paste0(CTGOV_API, "/", nct_id)

  tryCatch({
    response <- http_get_with_retry(url, timeout = 15)

    if (status_code(response) == 200) {
      fromJSON(content(response, "text", encoding = "UTF-8"), flatten = FALSE)
    } else {
      NULL
    }
  }, error = function(e) {
    warning("Error fetching study ", nct_id, ": ", e$message)
    NULL
  })
}

#' Calculate Recall
#'
#' @description Calculate recall of a search strategy against known included studies
#'
#' @param found_ncts Character vector of NCT IDs found by search
#' @param known_ncts Character vector of NCT IDs known to be relevant (gold standard)
#'
#' @return List with:
#' \describe{
#'   \item{total_known}{Number of known relevant studies}
#'   \item{total_found}{Number of studies found by search}
#'   \item{true_positives}{Number of known studies that were found}
#'   \item{recall}{Recall percentage (0-100)}
#'   \item{found_ids}{NCT IDs that were both known and found}
#'   \item{missed_ids}{Known NCT IDs not found by search}
#' }
#'
#' @export
#' @examples
#' known <- c("NCT00000001", "NCT00000002", "NCT00000003")
#' found <- c("NCT00000001", "NCT00000003", "NCT00000004", "NCT00000005")
#' metrics <- ctgov_calculate_recall(found, known)
#' print(paste0("Recall: ", metrics$recall, "%"))
ctgov_calculate_recall <- function(found_ncts, known_ncts) {

  # Normalize IDs
  known_ids <- unique(toupper(trimws(known_ncts[!is.na(known_ncts) & nchar(known_ncts) > 0])))
  found_ids <- unique(toupper(trimws(found_ncts[!is.na(found_ncts) & nchar(found_ncts) > 0])))

  if (length(known_ids) == 0) {
    return(list(
      total_known = 0,
      total_found = length(found_ids),
      true_positives = 0,
      recall = NA,
      found_ids = character(0),
      missed_ids = character(0)
    ))
  }

  # Calculate intersection
  true_positives <- intersect(known_ids, found_ids)
  missed <- setdiff(known_ids, found_ids)

  recall <- length(true_positives) / length(known_ids) * 100

  list(
    total_known = length(known_ids),
    total_found = length(found_ids),
    true_positives = length(true_positives),
    recall = round(recall, 2),
    found_ids = true_positives,
    missed_ids = missed
  )
}

#' Calculate Recall for Strategy
#'
#' @description Run a search strategy and calculate recall against known studies
#'
#' @param condition Condition to search
#' @param known_nct_ids Vector of NCT IDs known to be relevant
#' @param strategy Strategy ID (S1-S10)
#' @param max_results Maximum results to retrieve for comparison
#'
#' @return List with recall metrics and search results
#'
#' @export
#' @examples
#' \dontrun{
#' known <- c("NCT03702452", "NCT00400712")
#' metrics <- ctgov_strategy_recall("diabetes", known, strategy = "S1")
#' print(paste0("Strategy S1 recall: ", metrics$recall, "%"))
#' }
ctgov_strategy_recall <- function(condition, known_nct_ids, strategy = "S1",
                                  max_results = 1000) {

  # Execute search
  result <- ctgov_search(condition, strategy = strategy,
                         max_results = max_results, return_studies = TRUE)

  if (!is.null(result$error)) {
    return(list(
      strategy = strategy,
      strategy_name = result$strategy_name,
      condition = condition,
      total_known = length(known_nct_ids),
      total_found = 0,
      true_positives = 0,
      recall = NA,
      found_ids = character(0),
      missed_ids = known_nct_ids,
      error = result$error
    ))
  }

  # Calculate recall
  recall_metrics <- ctgov_calculate_recall(result$nct_ids, known_nct_ids)

  list(
    strategy = strategy,
    strategy_name = result$strategy_name,
    condition = condition,
    total_known = recall_metrics$total_known,
    total_found = recall_metrics$total_found,
    true_positives = recall_metrics$true_positives,
    recall = recall_metrics$recall,
    found_ids = recall_metrics$found_ids,
    missed_ids = recall_metrics$missed_ids,
    error = NULL
  )
}

#' Search with Synonym Expansion
#'
#' @description Search using condition and all known synonyms (OR logic)
#'
#' @param condition Base condition to search
#' @param strategy Strategy to use. Default is S1.
#' @param custom_synonyms Optional character vector of additional synonyms
#'
#' @return Search result with expanded query
#'
#' @export
#' @examples
#' \dontrun{
#' # Use built-in synonyms
#' result <- ctgov_search_with_synonyms("diabetes")
#'
#' # Add custom synonyms
#' result <- ctgov_search_with_synonyms("diabetes",
#'                                       custom_synonyms = c("glycemic disorder"))
#' }
ctgov_search_with_synonyms <- function(condition, strategy = "S1",
                                       custom_synonyms = NULL) {

  # Get synonyms
  synonyms <- SYNONYMS[[tolower(condition)]] %||% character(0)
  all_terms <- unique(c(condition, synonyms, custom_synonyms))

  if (length(all_terms) == 1) {
    result <- ctgov_search(condition, strategy = strategy)
    result$synonyms_used <- all_terms
    return(result)
  }

  # Build OR query
  or_query <- paste0('"', all_terms, '"', collapse = " OR ")

  # Modify query based on strategy
  if (strategy == "S9") {
    # Full-text search with synonyms
    url <- paste0(CTGOV_API, "?query.term=",
                  URLencode(paste0("(", or_query, ") AND randomized AND controlled"),
                            reserved = TRUE),
                  "&countTotal=true&pageSize=1")
  } else {
    # Condition-based strategies
    strat <- STRATEGIES[[strategy]]
    base_query <- strat$build_query("PLACEHOLDER", NULL)
    query <- gsub("query.cond=PLACEHOLDER",
                  paste0("query.cond=", URLencode(or_query, reserved = TRUE)),
                  base_query)
    url <- paste0(CTGOV_API, "?", query, "&countTotal=true&pageSize=1")
  }

  start_time <- Sys.time()

  tryCatch({
    response <- http_get_with_retry(url)
    parsed <- parse_ctgov_response(response)

    list(
      strategy_id = paste0(strategy, "_synonyms"),
      strategy_name = paste0("Synonym Expanded (", length(all_terms), " terms)"),
      condition = condition,
      synonyms_used = all_terms,
      total_count = parsed$total_count %||% 0,
      url = url,
      execution_time = as.numeric(difftime(Sys.time(), start_time, units = "secs")),
      error = parsed$error
    )
  }, error = function(e) {
    list(
      strategy_id = paste0(strategy, "_synonyms"),
      strategy_name = "Synonym Expanded",
      condition = condition,
      synonyms_used = all_terms,
      total_count = NA,
      url = url,
      execution_time = as.numeric(difftime(Sys.time(), start_time, units = "secs")),
      error = e$message
    )
  })
}

#' Search by NCT IDs
#'
#' @description Search for specific NCT IDs
#'
#' @param nct_ids Character vector of NCT IDs
#' @param return_studies Logical. Whether to return full study details.
#'
#' @return Search result with matching studies
#'
#' @export
#' @examples
#' \dontrun{
#' ids <- c("NCT03702452", "NCT00400712")
#' result <- ctgov_search_by_nct_ids(ids, return_studies = TRUE)
#' }
ctgov_search_by_nct_ids <- function(nct_ids, return_studies = TRUE) {

  normalized <- normalize_nct_ids(nct_ids)
  valid_ids <- normalized$valid_ids

  if (length(valid_ids) == 0) {
    return(list(
      strategy_id = "NCT_LOOKUP",
      strategy_name = "NCT ID Lookup",
      condition = "N/A",
      total_count = 0,
      studies = NULL,
      nct_ids = character(0),
      url = CTGOV_API,
      execution_time = 0,
      error = if (length(normalized$invalid_ids) > 0) {
        paste("No valid NCT IDs. Invalid:", paste(normalized$invalid_ids, collapse = ", "))
      } else {
        "No NCT IDs provided"
      }
    ))
  }

  start_time <- Sys.time()
  all_studies <- NULL
  found_ncts <- character(0)

  # Batch in groups of 100
  batch_size <- 100

  tryCatch({
    for (batch_start in seq(1, length(valid_ids), by = batch_size)) {
      batch_end <- min(batch_start + batch_size - 1, length(valid_ids))
      batch <- valid_ids[batch_start:batch_end]

      id_query <- paste(batch, collapse = " OR ")
      page_size <- if (return_studies) length(batch) else 1

      url <- paste0(CTGOV_API, "?query.id=", URLencode(id_query, reserved = TRUE),
                    "&countTotal=true&pageSize=", page_size)

      response <- http_get_with_retry(url)
      parsed <- parse_ctgov_response(response)

      if (parsed$success && !is.null(parsed$studies)) {
        if (is.null(all_studies)) {
          all_studies <- parsed$studies
        } else {
          all_studies <- rbind(all_studies, parsed$studies)
        }
        found_ncts <- c(found_ncts, extract_nct_ids(parsed$studies))
      }

      if (batch_end < length(valid_ids)) {
        Sys.sleep(RATE_LIMIT_DELAY)
      }
    }

    found_ncts <- unique(found_ncts)

    list(
      strategy_id = "NCT_LOOKUP",
      strategy_name = "NCT ID Lookup",
      condition = "N/A",
      total_count = length(found_ncts),
      studies = if (return_studies) all_studies else NULL,
      nct_ids = found_ncts,
      url = CTGOV_API,
      execution_time = as.numeric(difftime(Sys.time(), start_time, units = "secs")),
      error = NULL
    )

  }, error = function(e) {
    list(
      strategy_id = "NCT_LOOKUP",
      strategy_name = "NCT ID Lookup",
      condition = "N/A",
      total_count = 0,
      studies = NULL,
      nct_ids = character(0),
      url = CTGOV_API,
      execution_time = as.numeric(difftime(Sys.time(), start_time, units = "secs")),
      error = e$message
    )
  })
}

# ==============================================================================
# Report Generation
# ==============================================================================

#' Generate Search Report
#'
#' @description Generate a formatted report comparing all strategies for a condition
#'
#' @param condition Condition to search
#' @param output_file Optional file path to save report
#'
#' @return Formatted report string (invisibly)
#'
#' @export
#' @examples
#' \dontrun{
#' # Print to console
#' ctgov_generate_report("diabetes")
#'
#' # Save to file
#' ctgov_generate_report("diabetes", output_file = "diabetes_report.txt")
#' }
ctgov_generate_report <- function(condition, output_file = NULL) {

  results <- ctgov_compare_strategies(condition, verbose = FALSE)
  baseline <- results$total_count[results$strategy_id == "S1"]

  report <- c(
    paste(rep("=", 70), collapse = ""),
    paste("CT.gov Search Strategy Report:", toupper(condition)),
    paste("Generated:", format(Sys.time(), "%Y-%m-%d %H:%M:%S")),
    paste(rep("=", 70), collapse = ""),
    "",
    sprintf("%-5s %-35s %10s %12s", "ID", "Strategy", "Count", "% Baseline"),
    paste(rep("-", 65), collapse = "")
  )

  for (i in 1:nrow(results)) {
    r <- results[i, ]
    pct <- if (!is.na(r$total_count) && !is.na(baseline) && baseline > 0) {
      sprintf("%.1f%%", r$total_count / baseline * 100)
    } else {
      "N/A"
    }

    count_str <- if (!is.na(r$total_count)) {
      format(r$total_count, big.mark = ",")
    } else {
      "ERROR"
    }

    report <- c(report, sprintf("%-5s %-35s %10s %12s",
                                r$strategy_id, r$strategy_name, count_str, pct))
  }

  report <- c(report, "",
              paste(rep("-", 70), collapse = ""),
              "STRATEGY DESCRIPTIONS:",
              paste(rep("-", 70), collapse = ""))

  for (strat_id in names(STRATEGIES)) {
    strat <- STRATEGIES[[strat_id]]
    report <- c(report, sprintf("%s: %s", strat_id, strat$desc))
  }

  report <- c(report, "",
              paste(rep("-", 70), collapse = ""),
              "RECOMMENDATIONS:",
              paste(rep("-", 70), collapse = ""),
              "- For systematic reviews: Use S1 (maximum recall)",
              "- For RCTs only: Use S3 (randomized allocation)",
              "- For published trials: Use S7 (interventional + completed)",
              "- For highest quality: Use S8 (RCT + Phase 3/4 + completed)",
              "")

  report_text <- paste(report, collapse = "\n")

  if (!is.null(output_file)) {
    writeLines(report_text, output_file)
    message("Report saved to: ", output_file)
  }

  cat(report_text)
  invisible(report_text)
}

#' Export Results to CSV
#'
#' @description Export search comparison results to CSV file
#'
#' @param results Data frame from ctgov_compare_strategies()
#' @param filepath Path to output CSV file
#'
#' @export
#' @examples
#' \dontrun{
#' results <- ctgov_compare_strategies("diabetes")
#' ctgov_export_csv(results, "diabetes_strategies.csv")
#' }
ctgov_export_csv <- function(results, filepath) {
  write.csv(results, filepath, row.names = FALSE)
  message("Results exported to: ", filepath)
}

# ==============================================================================
# Demo and Examples
# ==============================================================================

#' Run Demo
#'
#' @description Demonstrate package functionality with sample searches
#'
#' @export
#' @examples
#' \dontrun{
#' ctgov_demo()
#' }
ctgov_demo <- function() {
  cat("CT.gov Search R Package - Demo\n")
  cat(paste(rep("=", 50), collapse = ""), "\n\n")

  cat("1. Single search (diabetes, S1 - Maximum Recall):\n")
  r <- ctgov_search("diabetes", strategy = "S1")
  cat("   Total:", format(r$total_count, big.mark = ","), "studies\n")
  cat("   Time:", round(r$execution_time, 2), "seconds\n\n")

  cat("2. Comparing all 10 strategies (diabetes):\n")
  results <- ctgov_compare_strategies("diabetes", verbose = FALSE)
  print(results[, c("strategy_id", "strategy_name", "total_count", "pct_baseline")])

  cat("\n3. Synonym expansion (diabetes):\n")
  syn <- ctgov_search_with_synonyms("diabetes")
  cat("   Total with synonyms:", format(syn$total_count, big.mark = ","), "\n")
  cat("   Terms used:", paste(syn$synonyms_used, collapse = ", "), "\n")

  cat("\n4. Study details lookup:\n")
  study <- ctgov_get_study_details("NCT03702452")
  if (!is.null(study)) {
    title <- study$protocolSection$identificationModule$briefTitle
    cat("   NCT03702452:", substr(title, 1, 60), "...\n")
  }

  cat("\n5. Recall calculation example:\n")
  known <- c("NCT00000001", "NCT00000002", "NCT00000003")
  found <- c("NCT00000001", "NCT00000003", "NCT00000004")
  metrics <- ctgov_calculate_recall(found, known)
  cat("   Known:", metrics$total_known, "| Found:", metrics$true_positives,
      "| Recall:", metrics$recall, "%\n")

  cat("\n", paste(rep("=", 50), collapse = ""), "\n")
  cat("Demo complete! Package ready for use.\n")
  cat("\nKey functions:\n")
  cat("  - ctgov_search(condition, strategy)\n")
  cat("  - ctgov_compare_strategies(condition)\n")
  cat("  - ctgov_validate_nct_ids(nct_ids)\n")
  cat("  - ctgov_get_study_details(nct_id)\n")
  cat("  - ctgov_calculate_recall(found, known)\n")
  cat("  - ctgov_generate_report(condition)\n")
}

# ==============================================================================
# Package Information
# ==============================================================================

#' Package Version Information
#'
#' @description Get package version and configuration info
#'
#' @return List with version info
#'
#' @export
ctgov_info <- function() {
  list(
    package = "ctgov.search",
    version = "2.1.0",
    api_endpoint = CTGOV_API,
    strategies = length(STRATEGIES),
    timeout = DEFAULT_TIMEOUT,
    page_size = DEFAULT_PAGE_SIZE,
    rate_limit = RATE_LIMIT_DELAY,
    max_retries = MAX_RETRIES
  )
}

# ==============================================================================
# Legacy Function Aliases (backward compatibility)
# ==============================================================================

#' @rdname ctgov_search
#' @export
search_ctgov <- ctgov_search

#' @rdname ctgov_compare_strategies
#' @export
compare_all_strategies <- ctgov_compare_strategies

#' @rdname ctgov_validate_nct_ids
#' @export
validate_nct_ids <- ctgov_validate_nct_ids

#' @rdname ctgov_calculate_recall
#' @export
calculate_recall <- function(condition, known_nct_ids, strategy = "S1") {
  ctgov_strategy_recall(condition, known_nct_ids, strategy)
}

#' @rdname ctgov_get_study_details
#' @export
get_study_details <- ctgov_get_study_details

#' @rdname ctgov_search_with_synonyms
#' @export
search_with_synonyms <- ctgov_search_with_synonyms

#' @rdname ctgov_generate_report
#' @export
generate_search_report <- ctgov_generate_report

#' @rdname ctgov_demo
#' @export
demo_ctgov_search <- ctgov_demo
