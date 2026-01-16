#!/bin/bash
# CT.gov Search Strategy Validation using curl
# This script tests different search strategies and collects metrics

WORKER_URL="https://restless-term-5510.mahmood726.workers.dev/"
OUTPUT_DIR="C:/Users/user/Downloads/ctgov-search-strategies/output"

echo "======================================================================"
echo "CT.gov Search Strategy Validation"
echo "======================================================================"
echo ""

# Create results CSV
RESULTS_FILE="$OUTPUT_DIR/search_results.csv"
echo "condition,strategy,total_count,response_time_ms" > "$RESULTS_FILE"

# Test conditions
CONDITIONS=("diabetes" "hypertension" "cancer" "asthma" "stroke" "depression" "arthritis" "obesity")

# Function to run search and extract count
run_search() {
    local search_type="$1"
    local query_param="$2"
    local condition="$3"
    local strategy="$4"

    local url="https://clinicaltrials.gov/api/v2/studies?${query_param}&filter.studyType=INTERVENTIONAL&pageSize=1"
    local encoded_url=$(echo "$url" | sed 's/ /%20/g')
    local full_url="${WORKER_URL}?url=${encoded_url}"

    local start_time=$(date +%s%3N)
    local response=$(curl -s "$full_url" 2>/dev/null)
    local end_time=$(date +%s%3N)
    local duration=$((end_time - start_time))

    local total=$(echo "$response" | grep -o '"totalCount":[0-9]*' | grep -o '[0-9]*' | head -1)
    total=${total:-0}

    echo "$condition,$strategy,$total,$duration" >> "$RESULTS_FILE"
    echo "  $strategy: $total results (${duration}ms)"
}

# Run tests for each condition
for cond in "${CONDITIONS[@]}"; do
    echo ""
    echo "Testing: $cond"
    echo "----------------------------------------"

    # Strategy 1: Condition field search
    run_search "cond" "query.cond=$cond" "$cond" "condition_field"
    sleep 0.3

    # Strategy 2: Condition + Completed status
    run_search "cond_completed" "query.cond=$cond&filter.overallStatus=COMPLETED" "$cond" "condition_completed"
    sleep 0.3

    # Strategy 3: Full text search
    run_search "fulltext" "query.term=$cond" "$cond" "full_text"
    sleep 0.3

    # Strategy 4: Full text with randomized
    run_search "fulltext_rct" "query.term=$cond%20randomized" "$cond" "fulltext_randomized"
    sleep 0.3

    # Strategy 5: Title search
    run_search "title" "query.titles=$cond" "$cond" "title_search"
    sleep 0.3
done

echo ""
echo "======================================================================"
echo "RESULTS SUMMARY"
echo "======================================================================"
echo ""

# Calculate summaries using awk
echo "Results by Strategy:"
echo "--------------------"
tail -n +2 "$RESULTS_FILE" | awk -F',' '
{
    strategy[$2] += $3
    count[$2]++
}
END {
    for (s in strategy) {
        avg = strategy[s] / count[s]
        printf "%-25s avg: %8.0f results\n", s, avg
    }
}' | sort -t: -k2 -rn

echo ""
echo "Results by Condition (condition_field strategy):"
echo "------------------------------------------------"
grep "condition_field" "$RESULTS_FILE" | awk -F',' '{printf "%-15s %s results\n", $1, $3}' | sort -t' ' -k2 -rn

echo ""
echo "======================================================================"
echo "ANALYSIS"
echo "======================================================================"

# Get totals for analysis
total_cond=$(grep "condition_field" "$RESULTS_FILE" | awk -F',' '{sum+=$3} END {print sum}')
total_completed=$(grep "condition_completed" "$RESULTS_FILE" | awk -F',' '{sum+=$3} END {print sum}')
total_fulltext=$(grep "full_text" "$RESULTS_FILE" | grep -v "randomized" | awk -F',' '{sum+=$3} END {print sum}')
total_title=$(grep "title_search" "$RESULTS_FILE" | awk -F',' '{sum+=$3} END {print sum}')

echo ""
echo "Total results across all conditions:"
echo "  - Condition field search: $total_cond"
echo "  - Condition + Completed:  $total_completed"
echo "  - Full text search:       $total_fulltext"
echo "  - Title search:           $total_title"

if [ "$total_cond" -gt 0 ] && [ "$total_completed" -gt 0 ]; then
    reduction=$(echo "scale=1; (1 - $total_completed / $total_cond) * 100" | bc)
    echo ""
    echo "Adding 'COMPLETED' filter reduces results by ${reduction}%"
fi

echo ""
echo "======================================================================"
echo "RECOMMENDATIONS FOR SYSTEMATIC REVIEWS"
echo "======================================================================"
echo ""
echo "1. COMPREHENSIVE SEARCH (high sensitivity):"
echo "   Use: condition_field search"
echo "   Pros: Captures most trials"
echo "   Cons: More results to screen"
echo ""
echo "2. FOCUSED SEARCH (balanced):"
echo "   Use: condition_completed"
echo "   Pros: Only completed trials with potential results"
echo "   Cons: Misses ongoing trials"
echo ""
echo "3. HYBRID APPROACH (recommended):"
echo "   Step 1: condition_completed for main search"
echo "   Step 2: condition_field to catch ongoing trials"
echo "   Step 3: De-duplicate using NCT IDs"
echo ""
echo "Results saved to: $RESULTS_FILE"
echo ""
echo "=== Validation Complete ==="
