#!/usr/bin/env Rscript
# Extract NCT IDs and Study Identifiers from Cochrane Reviews
# For gold standard validation of search strategies

library(data.table)

cat("=======================================================\n")
cat("Extracting NCT IDs from Cochrane Systematic Reviews\n")
cat("=======================================================\n\n")

# Paths
data_dir <- "C:/Users/user/OneDrive - NHS/Documents/Pairwise70/data"
output_dir <- "C:/Users/user/Downloads/ctgov-search-strategies/data"

# Get all RDA files
rda_files <- list.files(data_dir, pattern = "\\.rda$", full.names = TRUE)
cat("Found", length(rda_files), "Cochrane review files\n\n")

# Storage for results
all_studies <- list()
all_nct_ids <- list()

# NCT ID pattern
nct_pattern <- "NCT[0-9]{8}"

# Process each file
for (i in seq_along(rda_files)) {
  file <- rda_files[i]
  dataset_id <- gsub("\\.rda$", "", basename(file))

  tryCatch({
    # Load data
    env <- new.env()
    load(file, envir = env)

    # Get the data object
    obj_names <- ls(envir = env)
    if (length(obj_names) == 0) next

    data <- get(obj_names[1], envir = env)

    if (!is.data.frame(data) && !is.data.table(data)) {
      if (is.list(data) && length(data) > 0) {
        data <- data[[1]]
      }
    }

    if (!is.data.frame(data) && !is.data.table(data)) next

    data <- as.data.table(data)

    # Get column names
    cols <- names(data)

    # Look for study identifiers in various columns
    study_col <- NULL
    for (col in c("Study", "study", "StudyID", "study_id", "Study.ID", "author", "Author")) {
      if (col %in% cols) {
        study_col <- col
        break
      }
    }

    if (is.null(study_col)) {
      study_col <- cols[1]  # Use first column as fallback
    }

    # Extract unique studies
    studies <- unique(as.character(data[[study_col]]))
    studies <- studies[!is.na(studies) & nchar(studies) > 0]

    # Look for NCT IDs in study names and any ID columns
    nct_ids <- character(0)

    # Search in study names
    for (study in studies) {
      matches <- regmatches(study, gregexpr(nct_pattern, study, ignore.case = TRUE))[[1]]
      if (length(matches) > 0) {
        nct_ids <- c(nct_ids, toupper(matches))
      }
    }

    # Search in all character columns for NCT IDs
    for (col in cols) {
      if (is.character(data[[col]]) || is.factor(data[[col]])) {
        col_text <- paste(as.character(data[[col]]), collapse = " ")
        matches <- regmatches(col_text, gregexpr(nct_pattern, col_text, ignore.case = TRUE))[[1]]
        if (length(matches) > 0) {
          nct_ids <- c(nct_ids, toupper(matches))
        }
      }
    }

    nct_ids <- unique(nct_ids)

    # Store results
    all_studies[[dataset_id]] <- data.table(
      dataset_id = dataset_id,
      study = studies,
      has_nct = grepl(nct_pattern, studies, ignore.case = TRUE)
    )

    if (length(nct_ids) > 0) {
      all_nct_ids[[dataset_id]] <- data.table(
        dataset_id = dataset_id,
        nct_id = nct_ids
      )
    }

    if (i %% 50 == 0) {
      cat("Processed", i, "/", length(rda_files), "files\n")
    }

  }, error = function(e) {
    # Skip problematic files
  })
}

# Combine results
cat("\nCombining results...\n")

studies_dt <- rbindlist(all_studies, fill = TRUE)
nct_dt <- if (length(all_nct_ids) > 0) rbindlist(all_nct_ids, fill = TRUE) else data.table()

# Summary statistics
cat("\n=======================================================\n")
cat("EXTRACTION SUMMARY\n")
cat("=======================================================\n")

cat("\nStudies extracted:", nrow(studies_dt), "\n")
cat("Unique studies:", length(unique(studies_dt$study)), "\n")
cat("Studies with NCT IDs in name:", sum(studies_dt$has_nct), "\n")

if (nrow(nct_dt) > 0) {
  cat("\nNCT IDs found:", nrow(nct_dt), "\n")
  cat("Unique NCT IDs:", length(unique(nct_dt$nct_id)), "\n")
  cat("Reviews with NCT IDs:", length(unique(nct_dt$dataset_id)), "\n")
}

# Parse study names to extract author-year pattern
cat("\nExtracting author-year patterns for CT.gov title search...\n")

# Common patterns: "Smith 2020", "Smith et al. 2020", "Smith 2020a"
author_year_pattern <- "^([A-Z][a-z]+)\\s*(et al\\.?)?\\s*(\\d{4})[a-z]?$"

studies_dt[, author := sub("\\s+\\d{4}.*$", "", study)]
studies_dt[, year := as.integer(sub("^.*?(\\d{4}).*$", "\\1", study))]
studies_dt[, valid_author_year := !is.na(year) & year >= 1900 & year <= 2030]

cat("Studies with valid author-year format:", sum(studies_dt$valid_author_year, na.rm = TRUE), "\n")

# Save outputs
cat("\nSaving outputs...\n")

fwrite(studies_dt, file.path(output_dir, "cochrane_studies_full.csv"))
cat("Saved: cochrane_studies_full.csv\n")

if (nrow(nct_dt) > 0) {
  # Make unique
  nct_unique <- unique(nct_dt)
  fwrite(nct_unique, file.path(output_dir, "cochrane_nct_ids.csv"))
  cat("Saved: cochrane_nct_ids.csv\n")

  # Also save just the unique NCT IDs for validation
  nct_list <- unique(nct_dt$nct_id)
  writeLines(nct_list, file.path(output_dir, "nct_ids_list.txt"))
  cat("Saved: nct_ids_list.txt (", length(nct_list), "NCT IDs)\n")
}

# Create summary by review
review_summary <- studies_dt[, .(
  n_studies = .N,
  n_with_nct = sum(has_nct),
  n_valid_author_year = sum(valid_author_year, na.rm = TRUE)
), by = dataset_id]

fwrite(review_summary, file.path(output_dir, "review_extraction_summary.csv"))
cat("Saved: review_extraction_summary.csv\n")

# Sample of NCT IDs for testing
if (nrow(nct_dt) > 0) {
  cat("\n=======================================================\n")
  cat("SAMPLE NCT IDs FOR VALIDATION\n")
  cat("=======================================================\n")

  sample_ncts <- head(unique(nct_dt$nct_id), 20)
  cat("\nFirst 20 NCT IDs found:\n")
  for (nct in sample_ncts) {
    cat("  ", nct, "\n")
  }
}

cat("\n=== Extraction Complete ===\n")
