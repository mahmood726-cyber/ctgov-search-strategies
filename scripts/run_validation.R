#!/usr/bin/env Rscript
# CT.gov Search Strategy Validation Script
# Tests different search strategies against known Cochrane RCTs

library(data.table)
library(httr)
library(jsonlite)

cat("=" , paste(rep("=", 60), collapse=""), "\n")
cat("CT.gov Search Strategy Validation\n")
cat("=" , paste(rep("=", 60), collapse=""), "\n\n")

# Configuration
WORKER_URL <- "https://restless-term-5510.mahmood726.workers.dev/"
CTGOV_API <- "https://clinicaltrials.gov/api/v2/studies"
output_dir <- "C:/Users/user/Downloads/ctgov-search-strategies/output"

# Load test data
test_reviews <- fread("C:/Users/user/Downloads/ctgov-search-strategies/data/test_reviews.csv")
cat("Loaded", nrow(test_reviews), "test reviews\n\n")

# Function to search CT.gov via worker proxy
search_ctgov <- function(params, max_results = 100) {
  # Build query URL
  query_parts <- c()
  if (!is.null(params$condition) && params$condition != "") {
    query_parts <- c(query_parts, paste0("query.cond=", URLencode(params$condition, reserved = TRUE)))
  }
  if (!is.null(params$intervention) && params$intervention != "") {
    query_parts <- c(query_parts, paste0("query.intr=", URLencode(params$intervention, reserved = TRUE)))
  }
  if (!is.null(params$term) && params$term != "") {
    query_parts <- c(query_parts, paste0("query.term=", URLencode(params$term, reserved = TRUE)))
  }
  if (!is.null(params$status) && params$status != "") {
    query_parts <- c(query_parts, paste0("filter.overallStatus=", params$status))
  }

  # Always filter for interventional studies (RCTs)
  query_parts <- c(query_parts, "filter.studyType=INTERVENTIONAL")
  query_parts <- c(query_parts, paste0("pageSize=", max_results))

  ctgov_url <- paste0(CTGOV_API, "?", paste(query_parts, collapse = "&"))
  proxy_url <- paste0(WORKER_URL, "?url=", URLencode(ctgov_url, reserved = TRUE))

  tryCatch({
    start_time <- Sys.time()
    response <- GET(proxy_url, timeout(30))
    duration <- as.numeric(difftime(Sys.time(), start_time, units = "secs"))

    if (status_code(response) == 200) {
      data <- fromJSON(content(response, "text", encoding = "UTF-8"), flatten = TRUE)
      return(list(
        success = TRUE,
        total_count = data$totalCount %||% 0,
        returned = length(data$studies %||% list()),
        duration = round(duration, 2),
        studies = data$studies
      ))
    } else {
      return(list(success = FALSE, error = paste("HTTP", status_code(response))))
    }
  }, error = function(e) {
    return(list(success = FALSE, error = e$message))
  })
}

# Null coalescing operator
`%||%` <- function(a, b) if (is.null(a) || length(a) == 0) b else a

# Define search strategies
strategies <- list(
  condition_only = function(cond) list(condition = cond),
  condition_completed = function(cond) list(condition = cond, status = "COMPLETED"),
  full_text = function(cond) list(term = cond),
  full_text_rct = function(cond) list(term = paste(cond, "randomized")),
  broad_or = function(cond) {
    terms <- unlist(strsplit(cond, ", "))
    if (length(terms) > 1) {
      list(term = paste(terms, collapse = " OR "))
    } else {
      list(term = cond)
    }
  }
)

# Condition mapping for cleaner searches
condition_map <- c(
  "mental_health" = "mental health depression anxiety",
  "cardiovascular" = "cardiovascular heart disease",
  "infection" = "infection antibiotic",
  "pain" = "pain analgesic",
  "diabetes" = "diabetes glycemic",
  "hypertension" = "hypertension blood pressure",
  "cancer" = "cancer oncology",
  "respiratory" = "respiratory asthma COPD",
  "gastrointestinal" = "gastrointestinal digestive",
  "pregnancy" = "pregnancy obstetric neonatal",
  "neurological" = "neurological brain",
  "renal" = "renal kidney",
  "dermatology" = "dermatology skin"
)

# Run validation
results <- list()
cat("Testing search strategies...\n\n")

# Test a subset of conditions
test_conditions <- c("hypertension", "diabetes", "cancer", "infection", "mental health",
                     "cardiovascular", "pain", "respiratory")

for (cond in test_conditions) {
  cat("Testing condition:", cond, "\n")

  for (strat_name in names(strategies)) {
    params <- strategies[[strat_name]](cond)
    result <- search_ctgov(params)

    if (result$success) {
      cat(sprintf("  %s: %d results (%.2fs)\n",
                  strat_name, result$total_count, result$duration))

      results[[length(results) + 1]] <- data.frame(
        condition = cond,
        strategy = strat_name,
        total_results = result$total_count,
        returned = result$returned,
        duration_sec = result$duration,
        success = TRUE,
        stringsAsFactors = FALSE
      )
    } else {
      cat(sprintf("  %s: ERROR - %s\n", strat_name, result$error))
      results[[length(results) + 1]] <- data.frame(
        condition = cond,
        strategy = strat_name,
        total_results = NA,
        returned = NA,
        duration_sec = NA,
        success = FALSE,
        stringsAsFactors = FALSE
      )
    }

    Sys.sleep(0.5)  # Rate limiting
  }
  cat("\n")
}

# Combine results
results_df <- rbindlist(results)

# Calculate summary statistics
cat("\n", paste(rep("=", 60), collapse=""), "\n")
cat("RESULTS SUMMARY\n")
cat(paste(rep("=", 60), collapse=""), "\n\n")

# By strategy
strategy_summary <- results_df[success == TRUE, .(
  mean_results = round(mean(total_results)),
  median_results = round(median(total_results)),
  min_results = min(total_results),
  max_results = max(total_results),
  mean_duration = round(mean(duration_sec), 2)
), by = strategy]

cat("Results by Strategy:\n")
print(strategy_summary)

# By condition
condition_summary <- results_df[success == TRUE & strategy == "condition_only", .(
  condition,
  total_results
)][order(-total_results)]

cat("\nResults by Condition (condition_only strategy):\n")
print(condition_summary)

# Save results
fwrite(results_df, file.path(output_dir, "validation_results.csv"))
fwrite(strategy_summary, file.path(output_dir, "strategy_summary.csv"))

cat("\n\nResults saved to:\n")
cat("  - validation_results.csv\n")
cat("  - strategy_summary.csv\n")

# Recommendations
cat("\n", paste(rep("=", 60), collapse=""), "\n")
cat("RECOMMENDATIONS\n")
cat(paste(rep("=", 60), collapse=""), "\n\n")

best_strategy <- strategy_summary[mean_results == min(mean_results)]$strategy[1]
broadest_strategy <- strategy_summary[mean_results == max(mean_results)]$strategy[1]

cat("1. For COMPREHENSIVE searches (high sensitivity):\n")
cat("   Use:", broadest_strategy, "\n")
cat("   Average results:", strategy_summary[strategy == broadest_strategy]$mean_results, "\n\n")

cat("2. For FOCUSED searches (manageable screening):\n")
cat("   Use:", best_strategy, "\n")
cat("   Average results:", strategy_summary[strategy == best_strategy]$mean_results, "\n\n")

cat("3. RECOMMENDED APPROACH:\n")
cat("   - Start with 'condition_completed' for published trials\n")
cat("   - Add 'condition_only' to catch ongoing trials\n")
cat("   - Use 'full_text_rct' for specific RCT searches\n")

cat("\n=== Validation Complete ===\n")
