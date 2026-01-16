#!/usr/bin/env Rscript
# Extract condition keywords from analysis names for CT.gov search strategies

library(data.table)

# Load extracted studies
studies <- fread("C:/Users/user/Downloads/ctgov-search-strategies/data/extracted_studies.csv")
reviews <- fread("C:/Users/user/Downloads/ctgov-search-strategies/data/reviews_summary.csv")

cat("Extracting condition keywords from", nrow(reviews), "reviews\n\n")

# Medical condition keyword patterns
condition_patterns <- c(
  "hypertension" = "hypertens|blood pressure|bp",
  "diabetes" = "diabet|glyc|insulin|glucose",
  "cancer" = "cancer|carcinoma|tumor|tumour|neoplasm|oncol|malignan",
  "cardiovascular" = "cardiac|heart|myocard|coronary|stroke|vascular|athero",
  "respiratory" = "asthma|copd|pulmon|bronch|respirat|lung",
  "infection" = "infect|antibiot|sepsis|pneumonia|tuberc",
  "pregnancy" = "pregnan|perinatal|neonat|obstet|caesarean|delivery|preterm|infant|birth",
  "mental_health" = "depress|anxiety|schizoph|bipolar|psych|mental",
  "pain" = "pain|analges|arthrit|fibromyalg",
  "gastrointestinal" = "gastro|hepat|liver|colon|bowel|digest",
  "neurological" = "neuro|parkinson|alzheimer|epilep|dementia|stroke",
  "renal" = "renal|kidney|dialysis|nephro",
  "dermatology" = "skin|dermat|eczema|psoriasis"
)

# Extract conditions for each review
extract_conditions <- function(analysis_names, subgroups) {
  text <- tolower(paste(analysis_names, subgroups, collapse = " "))
  detected <- character()

  for (cond in names(condition_patterns)) {
    if (grepl(condition_patterns[cond], text, ignore.case = TRUE)) {
      detected <- c(detected, cond)
    }
  }

  if (length(detected) == 0) detected <- "other"
  paste(detected, collapse = ", ")
}

# Get unique analyses per review
review_conditions <- studies[, .(
  conditions = extract_conditions(
    unique(analysis_names),
    unique(subgroups)
  ),
  n_studies = .N,
  sample_analyses = paste(head(unique(analysis_names), 2), collapse = " | ")
), by = .(dataset_id, review_doi)]

# Add search keywords
review_conditions[, search_keywords := gsub(", ", " OR ", conditions)]

# Summary
cat("Condition distribution:\n")
print(table(unlist(strsplit(review_conditions$conditions, ", "))))

# Save
fwrite(review_conditions, "C:/Users/user/Downloads/ctgov-search-strategies/data/review_conditions.csv")
cat("\nSaved review_conditions.csv with", nrow(review_conditions), "reviews\n")

# Create a test set with clear conditions for validation
clear_conditions <- review_conditions[!grepl("other", conditions) & nchar(conditions) < 30]
set.seed(123)
test_set <- clear_conditions[sample(.N, min(30, .N))]
fwrite(test_set, "C:/Users/user/Downloads/ctgov-search-strategies/data/test_reviews.csv")
cat("Saved test_reviews.csv with", nrow(test_set), "reviews for validation\n")

cat("\n=== Sample test reviews ===\n")
print(head(test_set[, .(dataset_id, conditions, sample_analyses)], 10))
