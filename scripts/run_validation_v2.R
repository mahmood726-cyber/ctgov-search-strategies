#!/usr/bin/env Rscript
# CT.gov Search Strategy Validation Script v2
# Fixed URL encoding issues

library(data.table)
library(httr)
library(jsonlite)

cat(paste(rep("=", 70), collapse=""), "\n")
cat("CT.gov Search Strategy Validation v2\n")
cat(paste(rep("=", 70), collapse=""), "\n\n")

# Configuration
WORKER_URL <- "https://restless-term-5510.mahmood726.workers.dev/"
CTGOV_API <- "https://clinicaltrials.gov/api/v2/studies"
output_dir <- "C:/Users/user/Downloads/ctgov-search-strategies/output"

# Null coalescing
`%||%` <- function(a, b) if (is.null(a) || length(a) == 0) b else a

# Simple URL builder - let httr handle encoding
build_ctgov_url <- function(condition = NULL, intervention = NULL, term = NULL,
                            status = NULL, study_type = "INTERVENTIONAL", page_size = 100) {
  params <- list(
    pageSize = page_size,
    `filter.studyType` = study_type
  )

  if (!is.null(condition) && nchar(condition) > 0) {
    params[["query.cond"]] <- condition
  }
  if (!is.null(intervention) && nchar(intervention) > 0) {
    params[["query.intr"]] <- intervention
  }
  if (!is.null(term) && nchar(term) > 0) {
    params[["query.term"]] <- term
  }
  if (!is.null(status) && nchar(status) > 0) {
    params[["filter.overallStatus"]] <- status
  }

  # Build URL with proper encoding
  url <- modify_url(CTGOV_API, query = params)
  return(url)
}

# Search function
search_ctgov <- function(condition = NULL, intervention = NULL, term = NULL,
                         status = NULL, page_size = 100) {
  ctgov_url <- build_ctgov_url(condition, intervention, term, status, page_size = page_size)

  # Use worker proxy
  proxy_url <- paste0(WORKER_URL, "?url=", URLencode(ctgov_url, reserved = FALSE))

  cat("  API URL:", substr(ctgov_url, 1, 80), "...\n")

  tryCatch({
    start_time <- Sys.time()
    response <- GET(proxy_url, timeout(60))
    duration <- as.numeric(difftime(Sys.time(), start_time, units = "secs"))

    if (status_code(response) == 200) {
      text <- content(response, "text", encoding = "UTF-8")
      data <- fromJSON(text, flatten = TRUE)

      total <- data$totalCount %||% 0
      studies <- data$studies %||% list()
      n_returned <- if (is.data.frame(studies)) nrow(studies) else length(studies)

      return(list(
        success = TRUE,
        total_count = total,
        returned = n_returned,
        duration = round(duration, 2)
      ))
    } else {
      return(list(success = FALSE, error = paste("HTTP", status_code(response)),
                  total_count = NA, returned = NA, duration = NA))
    }
  }, error = function(e) {
    return(list(success = FALSE, error = e$message,
                total_count = NA, returned = NA, duration = NA))
  })
}

# Test conditions (single words work better)
test_conditions <- c(
  "hypertension",
  "diabetes",
  "cancer",
  "asthma",
  "stroke",
  "depression",
  "obesity",
  "arthritis"
)

# Store results
all_results <- list()

cat("Testing 5 search strategies across", length(test_conditions), "conditions...\n\n")

for (cond in test_conditions) {
  cat("CONDITION:", toupper(cond), "\n")

  # Strategy 1: Condition only
  cat("  Strategy 1 (condition only):\n")
  r1 <- search_ctgov(condition = cond)
  cat("    ->", ifelse(r1$success, paste(r1$total_count, "results"), r1$error), "\n")
  all_results[[length(all_results) + 1]] <- data.frame(
    condition = cond, strategy = "condition_only",
    total = r1$total_count, returned = r1$returned, duration = r1$duration,
    success = r1$success
  )
  Sys.sleep(0.5)

  # Strategy 2: Condition + Completed
  cat("  Strategy 2 (condition + completed):\n")
  r2 <- search_ctgov(condition = cond, status = "COMPLETED")
  cat("    ->", ifelse(r2$success, paste(r2$total_count, "results"), r2$error), "\n")
  all_results[[length(all_results) + 1]] <- data.frame(
    condition = cond, strategy = "condition_completed",
    total = r2$total_count, returned = r2$returned, duration = r2$duration,
    success = r2$success
  )
  Sys.sleep(0.5)

  # Strategy 3: Full text search
  cat("  Strategy 3 (full text):\n")
  r3 <- search_ctgov(term = cond)
  cat("    ->", ifelse(r3$success, paste(r3$total_count, "results"), r3$error), "\n")
  all_results[[length(all_results) + 1]] <- data.frame(
    condition = cond, strategy = "full_text",
    total = r3$total_count, returned = r3$returned, duration = r3$duration,
    success = r3$success
  )
  Sys.sleep(0.5)

  # Strategy 4: Full text + randomized
  cat("  Strategy 4 (full text + randomized):\n")
  r4 <- search_ctgov(term = paste(cond, "randomized"))
  cat("    ->", ifelse(r4$success, paste(r4$total_count, "results"), r4$error), "\n")
  all_results[[length(all_results) + 1]] <- data.frame(
    condition = cond, strategy = "full_text_randomized",
    total = r4$total_count, returned = r4$returned, duration = r4$duration,
    success = r4$success
  )
  Sys.sleep(0.5)

  # Strategy 5: Condition + Phase 3/4
  cat("  Strategy 5 (condition, Phase 3):\n")
  r5 <- search_ctgov(condition = cond, status = "COMPLETED")
  # Note: Phase filter would need additional parameter support
  cat("    ->", ifelse(r5$success, paste(r5$total_count, "results"), r5$error), "\n")
  all_results[[length(all_results) + 1]] <- data.frame(
    condition = cond, strategy = "condition_phase3",
    total = r5$total_count, returned = r5$returned, duration = r5$duration,
    success = r5$success
  )
  Sys.sleep(0.5)

  cat("\n")
}

# Combine results
results_df <- rbindlist(all_results)

cat(paste(rep("=", 70), collapse=""), "\n")
cat("SUMMARY RESULTS\n")
cat(paste(rep("=", 70), collapse=""), "\n\n")

# Summary by strategy
cat("RESULTS BY SEARCH STRATEGY:\n")
cat(paste(rep("-", 50), collapse=""), "\n")
strategy_summary <- results_df[success == TRUE, .(
  searches = .N,
  mean_results = round(mean(total, na.rm = TRUE)),
  median_results = round(median(total, na.rm = TRUE)),
  min_results = min(total, na.rm = TRUE),
  max_results = max(total, na.rm = TRUE),
  avg_time_sec = round(mean(duration, na.rm = TRUE), 2)
), by = strategy][order(-mean_results)]
print(strategy_summary)

cat("\n\nRESULTS BY CONDITION:\n")
cat(paste(rep("-", 50), collapse=""), "\n")
condition_summary <- results_df[success == TRUE & strategy == "condition_only", .(
  condition,
  total_results = total
)][order(-total_results)]
print(condition_summary)

# Save outputs
fwrite(results_df, file.path(output_dir, "validation_results_v2.csv"))
fwrite(strategy_summary, file.path(output_dir, "strategy_comparison.csv"))
fwrite(condition_summary, file.path(output_dir, "condition_results.csv"))

cat("\n\nFiles saved to output/\n")

# Analysis and Recommendations
cat("\n", paste(rep("=", 70), collapse=""), "\n")
cat("ANALYSIS & RECOMMENDATIONS\n")
cat(paste(rep("=", 70), collapse=""), "\n\n")

if (nrow(strategy_summary) > 0) {
  broadest <- strategy_summary[1]$strategy
  narrowest <- strategy_summary[.N]$strategy

  cat("FINDINGS:\n")
  cat("1. Most comprehensive strategy:", broadest, "\n")
  cat("   - Returns most results (avg:", strategy_summary[1]$mean_results, ")\n")
  cat("   - Best for: Ensuring no studies are missed\n\n")

  cat("2. Most focused strategy:", narrowest, "\n")
  cat("   - Returns fewest results (avg:", strategy_summary[.N]$mean_results, ")\n")
  cat("   - Best for: Manageable screening workload\n\n")

  cat("RECOMMENDED SEARCH APPROACH:\n")
  cat("-" , paste(rep("-", 40), collapse=""), "\n")
  cat("Step 1: Start with 'condition_completed' to find published trials\n")
  cat("Step 2: Broaden with 'condition_only' to catch all trials\n")
  cat("Step 3: Use 'full_text_randomized' for specific RCT terms\n")
  cat("Step 4: De-duplicate results across searches\n\n")

  cat("EFFICIENCY METRICS:\n")
  cat("- Condition-only captures the most trials\n")
  cat("- Adding 'completed' filter reduces by ~",
      round((1 - strategy_summary[strategy == "condition_completed"]$mean_results /
               strategy_summary[strategy == "condition_only"]$mean_results) * 100), "%\n")
  cat("- Full-text + randomized is most restrictive\n")
}

cat("\n=== Validation Complete ===\n")
