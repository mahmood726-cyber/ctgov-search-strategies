#!/usr/bin/env Rscript
# Extract study information from Cochrane pairwise meta-analysis RDS files
# Purpose: Create a dataset of known RCTs for CT.gov search strategy validation

library(data.table)

# Configuration
rds_dir <- "C:/Users/user/OneDrive - NHS/Documents/Pairwise70/analysis/output/cleaned_rds"
output_dir <- "C:/Users/user/Downloads/ctgov-search-strategies/data"

cat(paste(rep("=", 60), collapse=""), "\n")
cat("Extracting Cochrane Study Data for CT.gov Search Strategy Project\n")
cat(paste(rep("=", 60), collapse=""), "\n\n")

# Get all RDS files
rds_files <- list.files(rds_dir, pattern = "\\.rds$", full.names = TRUE)
cat("Found", length(rds_files), "RDS files\n\n")

# Extract data from each file
all_studies <- list()
all_reviews <- list()

for (i in seq_along(rds_files)) {
  file <- rds_files[i]
  dataset_id <- sub("\\.rds$", "", basename(file))

  tryCatch({
    df <- readRDS(file)

    # Extract unique studies
    if ("Study" %in% names(df)) {
      studies <- unique(df[, c("Study", "Study.year"), drop = FALSE])
      studies$dataset_id <- dataset_id

      # Extract review info
      if ("review.doi" %in% names(df)) {
        studies$review_doi <- df$review.doi[1]
      }
      if ("review.url" %in% names(df)) {
        studies$review_url <- df$review.url[1]
      }

      # Extract analysis names (gives hints about conditions/interventions)
      if ("Analysis.name" %in% names(df)) {
        analysis_names <- unique(na.omit(df$Analysis.name))
        studies$analysis_names <- paste(analysis_names, collapse = " | ")
      }

      # Extract subgroups (more condition info)
      if ("Subgroup" %in% names(df)) {
        subgroups <- unique(na.omit(df$Subgroup))
        subgroups <- subgroups[subgroups != ""]
        studies$subgroups <- paste(subgroups, collapse = " | ")
      }

      all_studies[[dataset_id]] <- studies
    }

    # Extract review-level info
    review_info <- data.frame(
      dataset_id = dataset_id,
      n_studies = length(unique(df$Study)),
      n_analyses = length(unique(paste(df$Analysis.group, df$Analysis.number))),
      stringsAsFactors = FALSE
    )
    if ("review.doi" %in% names(df)) review_info$review_doi <- df$review.doi[1]
    if ("review.url" %in% names(df)) review_info$review_url <- df$review.url[1]

    all_reviews[[dataset_id]] <- review_info

  }, error = function(e) {
    cat("Error processing", basename(file), ":", e$message, "\n")
  })

  if (i %% 50 == 0) cat("Processed", i, "of", length(rds_files), "files\n")
}

# Combine results
studies_df <- rbindlist(all_studies, fill = TRUE)
reviews_df <- rbindlist(all_reviews, fill = TRUE)

cat("\n--- Summary ---\n")
cat("Total unique study entries:", nrow(studies_df), "\n")
cat("Total reviews:", nrow(reviews_df), "\n")

# Get truly unique studies (by name + year)
unique_studies <- unique(studies_df[, c("Study", "Study.year")])
cat("Unique study-year combinations:", nrow(unique_studies), "\n")

# Parse study names to extract author and year for searching
studies_df$author_name <- gsub("\\s+\\d{4}.*$", "", studies_df$Study)
studies_df$parsed_year <- as.integer(gsub("^.*\\s+(\\d{4}).*$", "\\1", studies_df$Study))

# Save outputs
fwrite(studies_df, file.path(output_dir, "extracted_studies.csv"))
fwrite(reviews_df, file.path(output_dir, "reviews_summary.csv"))
fwrite(unique_studies, file.path(output_dir, "unique_studies.csv"))

cat("\nSaved:\n")
cat("  - extracted_studies.csv (", nrow(studies_df), " rows)\n")
cat("  - reviews_summary.csv (", nrow(reviews_df), " rows)\n")
cat("  - unique_studies.csv (", nrow(unique_studies), " rows)\n")

# Create a sample for initial testing
set.seed(42)
sample_reviews <- reviews_df[sample(.N, min(20, .N))]
fwrite(sample_reviews, file.path(output_dir, "sample_reviews.csv"))
cat("  - sample_reviews.csv (", nrow(sample_reviews), " rows for testing)\n")

# Extract Cochrane IDs for DOI lookup
reviews_df$cochrane_id <- gsub("^.*/(CD\\d+)\\.pub.*$", "\\1", reviews_df$review_doi)
cochrane_ids <- unique(reviews_df$cochrane_id)
cat("\nUnique Cochrane review IDs:", length(cochrane_ids), "\n")
cat("Sample IDs:", paste(head(cochrane_ids, 5), collapse = ", "), "\n")

cat("\n=== Extraction Complete ===\n")
