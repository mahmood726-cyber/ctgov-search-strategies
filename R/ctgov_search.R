#' CT.gov Search Strategy Functions for R
#' Comprehensive interface for ClinicalTrials.gov API v2
#'
#' Based on Cochrane guidance and empirical validation
#' @author CT.gov Search Strategy Project

library(httr)
library(jsonlite)
library(data.table)

# API Configuration
CTGOV_API <- "https://clinicaltrials.gov/api/v2/studies"
RATE_LIMIT_DELAY <- 0.3

#' Search Strategies Definition
#' @export
STRATEGIES <- list(
  S1 = list(
    name = "Condition Only (Maximum Recall)",
    desc = "Cochrane recommended - no filters",
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
    desc = "True RCTs - excludes single-arm",
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
    desc = "Studies with results on CT.gov",
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
    desc = "Highest quality subset",
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
    desc = "Text: condition AND randomized AND controlled",
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

#' MeSH Synonyms for Common Conditions
SYNONYMS <- list(
  diabetes = c("diabetes mellitus", "diabetic", "type 2 diabetes", "type 1 diabetes"),
  hypertension = c("high blood pressure", "elevated blood pressure", "HTN"),
  depression = c("major depressive disorder", "MDD", "depressive disorder"),
  `heart failure` = c("cardiac failure", "CHF", "congestive heart failure"),
  stroke = c("cerebrovascular accident", "CVA", "brain infarction"),
  `breast cancer` = c("breast neoplasm", "breast carcinoma", "mammary cancer"),
  asthma = c("bronchial asthma", "asthmatic")
)

#' Search CT.gov using specified strategy
#'
#' @param condition Character string of condition/disease
#' @param strategy Strategy ID (S1-S10), default S1
#' @param intervention Optional intervention filter
#' @param page_size Number of results to return (max 1000)
#' @param return_studies Whether to return study details
#' @return List with total_count, studies, url, and timing
#' @export
#' @examples
#' search_ctgov("diabetes", strategy = "S1")
#' search_ctgov("breast cancer", strategy = "S3")
search_ctgov <- function(condition, strategy = "S1", intervention = NULL,
                          page_size = 100, return_studies = FALSE) {

  if (!strategy %in% names(STRATEGIES)) {
    stop(paste("Unknown strategy:", strategy, ". Valid:", paste(names(STRATEGIES), collapse = ", ")))
  }

  strat <- STRATEGIES[[strategy]]
  query <- strat$build_query(condition, intervention)

  url <- paste0(CTGOV_API, "?", query, "&countTotal=true&pageSize=", page_size)

  start_time <- Sys.time()

  tryCatch({
    response <- GET(url, timeout(30))

    if (status_code(response) == 200) {
      data <- fromJSON(content(response, "text", encoding = "UTF-8"), flatten = TRUE)

      list(
        strategy_id = strategy,
        strategy_name = strat$name,
        condition = condition,
        total_count = data$totalCount %||% 0,
        studies = if (return_studies) data$studies else NULL,
        url = url,
        execution_time = as.numeric(difftime(Sys.time(), start_time, units = "secs")),
        error = NULL
      )
    } else {
      list(
        strategy_id = strategy,
        strategy_name = strat$name,
        condition = condition,
        total_count = NA,
        studies = NULL,
        url = url,
        execution_time = as.numeric(difftime(Sys.time(), start_time, units = "secs")),
        error = paste("HTTP", status_code(response))
      )
    }
  }, error = function(e) {
    list(
      strategy_id = strategy,
      strategy_name = strat$name,
      condition = condition,
      total_count = NA,
      studies = NULL,
      url = url,
      execution_time = as.numeric(difftime(Sys.time(), start_time, units = "secs")),
      error = e$message
    )
  })
}

#' Compare all strategies for a condition
#'
#' @param condition Condition to search
#' @param intervention Optional intervention
#' @return data.table with results from all strategies
#' @export
compare_all_strategies <- function(condition, intervention = NULL) {

  results <- list()

  for (strat_id in names(STRATEGIES)) {
    cat("Testing", strat_id, "...\n")
    result <- search_ctgov(condition, strategy = strat_id, intervention = intervention)
    results[[strat_id]] <- data.table(
      strategy_id = result$strategy_id,
      strategy_name = result$strategy_name,
      condition = result$condition,
      total_count = result$total_count,
      execution_time = result$execution_time,
      url = result$url,
      error = result$error %||% ""
    )
    Sys.sleep(RATE_LIMIT_DELAY)
  }

  rbindlist(results)
}

#' Validate NCT IDs exist on CT.gov
#'
#' @param nct_ids Character vector of NCT IDs
#' @return data.table with nct_id and exists columns
#' @export
validate_nct_ids <- function(nct_ids) {

  results <- list()

  for (i in seq_along(nct_ids)) {
    nct_id <- toupper(trimws(nct_ids[i]))

    if (!grepl("^NCT\\d{8}$", nct_id)) {
      results[[i]] <- data.table(nct_id = nct_id, exists = FALSE, error = "Invalid format")
      next
    }

    url <- paste0(CTGOV_API, "?query.id=", nct_id, "&countTotal=true&pageSize=1")

    tryCatch({
      response <- GET(url, timeout(15))
      data <- fromJSON(content(response, "text", encoding = "UTF-8"), flatten = TRUE)
      exists <- (data$totalCount %||% 0) > 0

      results[[i]] <- data.table(nct_id = nct_id, exists = exists, error = NA_character_)
    }, error = function(e) {
      results[[i]] <- data.table(nct_id = nct_id, exists = NA, error = e$message)
    })

    if (i %% 10 == 0) cat("Validated", i, "/", length(nct_ids), "\n")
    Sys.sleep(RATE_LIMIT_DELAY)
  }

  rbindlist(results)
}

#' Calculate recall against known NCT IDs
#'
#' @param condition Condition to search
#' @param known_nct_ids Vector of NCT IDs known to be relevant
#' @param strategy Strategy to test
#' @return List with recall metrics
#' @export
calculate_recall <- function(condition, known_nct_ids, strategy = "S1") {

  # Get studies from search
  result <- search_ctgov(condition, strategy = strategy, page_size = 1000, return_studies = TRUE)

  if (is.null(result$studies) || length(result$studies) == 0) {
    return(list(
      strategy = strategy,
      total_known = length(known_nct_ids),
      found = 0,
      recall = 0,
      found_ids = character(0),
      missed_ids = known_nct_ids
    ))
  }

  # Extract NCT IDs from results
  found_ids <- tryCatch({
    unique(result$studies$protocolSection.identificationModule.nctId)
  }, error = function(e) character(0))

  found_ids <- toupper(found_ids)
  known_ids <- toupper(trimws(known_nct_ids))

  found <- intersect(known_ids, found_ids)
  missed <- setdiff(known_ids, found_ids)

  list(
    strategy = strategy,
    total_known = length(known_ids),
    found = length(found),
    recall = length(found) / length(known_ids) * 100,
    found_ids = found,
    missed_ids = missed
  )
}

#' Search with synonym expansion
#'
#' @param condition Base condition
#' @return Search result with expanded query
#' @export
search_with_synonyms <- function(condition) {

  synonyms <- SYNONYMS[[tolower(condition)]]
  all_terms <- unique(c(condition, synonyms))

  if (length(all_terms) == 1) {
    return(search_ctgov(condition, strategy = "S1"))
  }

  # Build OR query
  or_query <- paste0('"', all_terms, '"', collapse = " OR ")

  url <- paste0(CTGOV_API, "?query.cond=", URLencode(or_query, reserved = TRUE),
                "&countTotal=true&pageSize=1")

  start_time <- Sys.time()

  tryCatch({
    response <- GET(url, timeout(30))
    data <- fromJSON(content(response, "text", encoding = "UTF-8"), flatten = TRUE)

    list(
      strategy_id = "S1_synonyms",
      strategy_name = paste0("Synonym Expanded (", length(all_terms), " terms)"),
      condition = condition,
      synonyms = all_terms,
      total_count = data$totalCount %||% 0,
      url = url,
      execution_time = as.numeric(difftime(Sys.time(), start_time, units = "secs"))
    )
  }, error = function(e) {
    list(
      strategy_id = "S1_synonyms",
      strategy_name = "Synonym Expanded",
      condition = condition,
      synonyms = all_terms,
      total_count = NA,
      url = url,
      error = e$message
    )
  })
}

#' Get study details by NCT ID
#'
#' @param nct_id NCT ID of study
#' @return Study details as list
#' @export
get_study_details <- function(nct_id) {
  url <- paste0(CTGOV_API, "/", nct_id)

  tryCatch({
    response <- GET(url, timeout(15))
    if (status_code(response) == 200) {
      fromJSON(content(response, "text", encoding = "UTF-8"), flatten = TRUE)
    } else {
      NULL
    }
  }, error = function(e) NULL)
}

#' Generate search report
#'
#' @param condition Condition to search
#' @param output_file Optional file path to save report
#' @return Formatted report string
#' @export
generate_search_report <- function(condition, output_file = NULL) {

  results <- compare_all_strategies(condition)
  baseline <- results[strategy_id == "S1"]$total_count

  report <- c(
    paste(rep("=", 70), collapse = ""),
    paste("CT.gov Search Strategy Report:", toupper(condition)),
    paste("Generated:", Sys.time()),
    paste(rep("=", 70), collapse = ""),
    "",
    sprintf("%-5s %-35s %10s %12s", "ID", "Strategy", "Count", "% Baseline"),
    paste(rep("-", 65), collapse = "")
  )

  for (i in 1:nrow(results)) {
    r <- results[i]
    pct <- if (!is.na(r$total_count) && baseline > 0) {
      sprintf("%.1f%%", r$total_count / baseline * 100)
    } else "N/A"

    count_str <- if (!is.na(r$total_count)) format(r$total_count, big.mark = ",") else "ERROR"
    report <- c(report, sprintf("%-5s %-35s %10s %12s",
                                r$strategy_id, r$strategy_name, count_str, pct))
  }

  report <- c(report, "", "RECOMMENDATIONS:",
              paste(rep("-", 40), collapse = ""),
              "- For systematic reviews: Use S1 (maximum recall)",
              "- For RCTs only: Use S3 (randomized allocation)",
              "- For published trials: Use S7 (interventional + completed)",
              "")

  report_text <- paste(report, collapse = "\n")

  if (!is.null(output_file)) {
    writeLines(report_text, output_file)
    cat("Report saved to:", output_file, "\n")
  }

  cat(report_text)
  invisible(report_text)
}

# Null coalescing operator
`%||%` <- function(a, b) if (is.null(a) || length(a) == 0 || (length(a) == 1 && is.na(a))) b else a

# Demo function
demo_ctgov_search <- function() {
  cat("CT.gov Search R Package - Demo\n")
  cat(paste(rep("=", 50), collapse = ""), "\n\n")

  cat("1. Single search (diabetes, S1):\n")
  r <- search_ctgov("diabetes", strategy = "S1")
  cat("   Total:", format(r$total_count, big.mark = ","), "studies\n\n")

  cat("2. Comparing strategies (diabetes):\n")
  results <- compare_all_strategies("diabetes")
  print(results[, .(strategy_id, strategy_name, total_count)])

  cat("\n3. Synonym expansion (diabetes):\n")
  syn <- search_with_synonyms("diabetes")
  cat("   Total with synonyms:", format(syn$total_count, big.mark = ","), "\n")
  cat("   Terms used:", paste(syn$synonyms, collapse = ", "), "\n")

  cat("\nDemo complete!\n")
}
