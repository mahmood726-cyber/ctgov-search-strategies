#!/bin/bash
# CT.gov Search Strategy Full Validation
# Using correct URL encoding for worker proxy

WORKER="https://restless-term-5510.mahmood726.workers.dev/"
OUTPUT_DIR="C:/Users/user/Downloads/ctgov-search-strategies/output"

echo "======================================================================"
echo "CT.gov Search Strategy Full Validation"
echo "======================================================================"
echo ""
echo "Testing different search strategies across multiple medical conditions"
echo ""

# Results file
RESULTS="$OUTPUT_DIR/full_validation_results.csv"
echo "condition,strategy,total_count,duration_ms" > "$RESULTS"

# Function to search CT.gov
search() {
    local condition="$1"
    local strategy="$2"
    local query="$3"

    # Build URL with correct encoding (only encode ? and &)
    local api_url="https://clinicaltrials.gov/api/v2/studies%3F${query}%26pageSize%3D1"
    local full_url="${WORKER}?url=${api_url}"

    local start=$(date +%s%N)
    local response=$(curl -s --max-time 30 "$full_url" 2>/dev/null)
    local end=$(date +%s%N)
    local duration=$(( (end - start) / 1000000 ))

    # Extract totalCount from JSON
    local count=$(echo "$response" | grep -oP '"totalCount"\s*:\s*\K[0-9]+' | head -1)
    count=${count:-0}

    echo "$condition,$strategy,$count,$duration" >> "$RESULTS"
    printf "  %-25s %8s results (%4dms)\n" "$strategy" "$count" "$duration"
}

# Test conditions
declare -a CONDITIONS=("diabetes" "hypertension" "cancer" "asthma" "stroke" "depression" "heart+failure" "covid")

for cond in "${CONDITIONS[@]}"; do
    echo ""
    echo "Condition: $cond"
    echo "----------------------------------------"

    # Strategy 1: Condition only (query.cond)
    search "$cond" "cond_only" "query.cond%3D${cond}"
    sleep 0.3

    # Strategy 2: Condition + Interventional (explicit)
    search "$cond" "cond_interventional" "query.cond%3D${cond}%26filter.studyType%3DINTERVENTIONAL"
    sleep 0.3

    # Strategy 3: Condition + Completed
    search "$cond" "cond_completed" "query.cond%3D${cond}%26filter.overallStatus%3DCOMPLETED"
    sleep 0.3

    # Strategy 4: Full text term search
    search "$cond" "term_search" "query.term%3D${cond}"
    sleep 0.3

    # Strategy 5: Title search
    search "$cond" "title_search" "query.titles%3D${cond}"
    sleep 0.3
done

echo ""
echo "======================================================================"
echo "SUMMARY BY STRATEGY"
echo "======================================================================"

# Aggregate results
echo ""
echo "Average results per strategy:"
echo "-----------------------------"
awk -F',' 'NR>1 {
    sum[$2]+=$3;
    count[$2]++
}
END {
    for(s in sum)
        printf "%-25s %10.0f avg results\n", s, sum[s]/count[s]
}' "$RESULTS" | sort -t'g' -k2 -rn

echo ""
echo "======================================================================"
echo "SUMMARY BY CONDITION"
echo "======================================================================"

echo ""
echo "Results for cond_only strategy:"
echo "-------------------------------"
grep "cond_only" "$RESULTS" | awk -F',' '{printf "%-20s %s\n", $1, $3}' | sort -t' ' -k2 -rn

echo ""
echo "======================================================================"
echo "DETAILED ANALYSIS"
echo "======================================================================"

# Calculate metrics
echo ""
total_cond=$(awk -F',' '$2=="cond_only" {sum+=$3} END {print sum}' "$RESULTS")
total_interv=$(awk -F',' '$2=="cond_interventional" {sum+=$3} END {print sum}' "$RESULTS")
total_completed=$(awk -F',' '$2=="cond_completed" {sum+=$3} END {print sum}' "$RESULTS")
total_term=$(awk -F',' '$2=="term_search" {sum+=$3} END {print sum}' "$RESULTS")
total_title=$(awk -F',' '$2=="title_search" {sum+=$3} END {print sum}' "$RESULTS")

echo "Total results across all conditions:"
echo "  Condition only:          $total_cond"
echo "  Condition+Interventional: $total_interv"
echo "  Condition+Completed:      $total_completed"
echo "  Term (full text):         $total_term"
echo "  Title search:             $total_title"

if [ "$total_cond" -gt 0 ]; then
    echo ""
    echo "Filter effectiveness (compared to cond_only):"

    if [ "$total_interv" -gt 0 ]; then
        reduction=$(awk "BEGIN {printf \"%.1f\", (1-$total_interv/$total_cond)*100}")
        echo "  Adding 'Interventional' filter: -${reduction}%"
    fi

    if [ "$total_completed" -gt 0 ]; then
        reduction=$(awk "BEGIN {printf \"%.1f\", (1-$total_completed/$total_cond)*100}")
        echo "  Adding 'Completed' filter:      -${reduction}%"
    fi
fi

echo ""
echo "======================================================================"
echo "RECOMMENDATIONS"
echo "======================================================================"
echo ""
echo "FOR SYSTEMATIC REVIEW SEARCHES:"
echo ""
echo "1. HIGH SENSITIVITY (find all relevant trials):"
echo "   Use: query.cond=<condition>"
echo "   Expected: Most results, highest recall"
echo ""
echo "2. BALANCED (published RCTs with results):"
echo "   Use: query.cond=<condition>&filter.overallStatus=COMPLETED"
echo "   Expected: ~30-50% fewer results, focused on completed trials"
echo ""
echo "3. PRECISE (specific RCT identification):"
echo "   Use: query.cond=<condition>&filter.studyType=INTERVENTIONAL"
echo "   Expected: Only interventional studies (RCTs, non-RCT interventional)"
echo ""
echo "4. RECOMMENDED WORKFLOW:"
echo "   a) Start with cond_completed for main search"
echo "   b) Add cond_only minus completed to get ongoing trials"
echo "   c) Deduplicate by NCT ID"
echo "   d) Screen results"
echo ""
echo "Results saved to: $RESULTS"
echo ""
echo "=== Validation Complete ==="
