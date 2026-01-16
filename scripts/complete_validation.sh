#!/bin/bash
# CT.gov Search Strategy Complete Validation
# Using correct API filter syntax

echo "======================================================================"
echo "CT.gov Search Strategy Validation - Complete"
echo "======================================================================"
echo ""

OUTPUT_DIR="C:/Users/user/Downloads/ctgov-search-strategies/output"
RESULTS="$OUTPUT_DIR/complete_validation.csv"

echo "condition,strategy,total_count" > "$RESULTS"

# Function to search CT.gov API
search_api() {
    local cond="$1"
    local strategy="$2"
    local url="$3"

    local response=$(curl -s --max-time 30 "$url" 2>/dev/null)
    local count=$(echo "$response" | sed 's/.*"totalCount":\([0-9]*\).*/\1/' | head -1)

    if [[ "$count" =~ ^[0-9]+$ ]]; then
        echo "$cond,$strategy,$count" >> "$RESULTS"
        printf "  %-35s %10s results\n" "$strategy" "$count"
    else
        echo "$cond,$strategy,ERROR" >> "$RESULTS"
        printf "  %-35s %10s\n" "$strategy" "ERROR"
    fi
}

# Test conditions
CONDITIONS=("diabetes" "hypertension" "cancer" "asthma" "stroke" "depression")

for cond in "${CONDITIONS[@]}"; do
    echo ""
    echo "CONDITION: $cond"
    echo "----------------------------------------"

    # Strategy 1: Condition only (all study types)
    url="https://clinicaltrials.gov/api/v2/studies?query.cond=${cond}&countTotal=true&pageSize=1"
    search_api "$cond" "all_studies" "$url"
    sleep 0.5

    # Strategy 2: Condition + Interventional (using AREA syntax)
    url="https://clinicaltrials.gov/api/v2/studies?query.cond=${cond}&filter.advanced=AREA%5BStudyType%5DINTERVENTIONAL&countTotal=true&pageSize=1"
    search_api "$cond" "interventional_only" "$url"
    sleep 0.5

    # Strategy 3: Condition + Completed
    url="https://clinicaltrials.gov/api/v2/studies?query.cond=${cond}&filter.overallStatus=COMPLETED&countTotal=true&pageSize=1"
    search_api "$cond" "completed_only" "$url"
    sleep 0.5

    # Strategy 4: Condition + Interventional + Completed
    url="https://clinicaltrials.gov/api/v2/studies?query.cond=${cond}&filter.advanced=AREA%5BStudyType%5DINTERVENTIONAL&filter.overallStatus=COMPLETED&countTotal=true&pageSize=1"
    search_api "$cond" "interventional_completed" "$url"
    sleep 0.5

    # Strategy 5: Full text search (query.term)
    url="https://clinicaltrials.gov/api/v2/studies?query.term=${cond}&countTotal=true&pageSize=1"
    search_api "$cond" "fulltext_search" "$url"
    sleep 0.5

    # Strategy 6: Full text + randomized
    url="https://clinicaltrials.gov/api/v2/studies?query.term=${cond}%20randomized&countTotal=true&pageSize=1"
    search_api "$cond" "fulltext_randomized" "$url"
    sleep 0.5
done

echo ""
echo "======================================================================"
echo "SUMMARY ANALYSIS"
echo "======================================================================"
echo ""

echo "AVERAGE BY STRATEGY:"
echo "--------------------"
awk -F',' 'NR>1 && $3!="ERROR" && $3 ~ /^[0-9]+$/ {
    sum[$2]+=$3
    count[$2]++
}
END {
    for(s in sum)
        printf "%-35s %10.0f avg\n", s, sum[s]/count[s]
}' "$RESULTS" | sort -t'g' -k2 -rn

echo ""
echo "BY CONDITION (all_studies):"
echo "---------------------------"
grep ",all_studies," "$RESULTS" | awk -F',' '{printf "%-15s %10s\n", $1, $3}' | sort -t' ' -k2 -rn

echo ""
echo "======================================================================"
echo "FILTER REDUCTION ANALYSIS"
echo "======================================================================"
echo ""

for cond in "${CONDITIONS[@]}"; do
    all=$(grep "^${cond},all_studies," "$RESULTS" | cut -d',' -f3)
    interv=$(grep "^${cond},interventional_only," "$RESULTS" | cut -d',' -f3)
    completed=$(grep "^${cond},completed_only," "$RESULTS" | cut -d',' -f3)
    both=$(grep "^${cond},interventional_completed," "$RESULTS" | cut -d',' -f3)

    if [[ "$all" =~ ^[0-9]+$ ]] && [ "$all" -gt 0 ]; then
        echo "$cond:"

        if [[ "$interv" =~ ^[0-9]+$ ]]; then
            pct=$(awk "BEGIN {printf \"%.1f\", ($interv/$all)*100}")
            red=$(awk "BEGIN {printf \"%.1f\", (1-$interv/$all)*100}")
            echo "  Interventional filter: $interv ($pct% retained, -${red}% reduction)"
        fi

        if [[ "$completed" =~ ^[0-9]+$ ]]; then
            pct=$(awk "BEGIN {printf \"%.1f\", ($completed/$all)*100}")
            red=$(awk "BEGIN {printf \"%.1f\", (1-$completed/$all)*100}")
            echo "  Completed filter:      $completed ($pct% retained, -${red}% reduction)"
        fi

        if [[ "$both" =~ ^[0-9]+$ ]]; then
            pct=$(awk "BEGIN {printf \"%.1f\", ($both/$all)*100}")
            red=$(awk "BEGIN {printf \"%.1f\", (1-$both/$all)*100}")
            echo "  Both filters:          $both ($pct% retained, -${red}% reduction)"
        fi
        echo ""
    fi
done

echo "======================================================================"
echo "RECOMMENDATIONS FOR SYSTEMATIC REVIEWS"
echo "======================================================================"
echo ""
echo "SEARCH STRATEGY RANKING:"
echo ""
echo "1. MAXIMUM RECALL (miss nothing):"
echo "   query.cond=<condition>"
echo "   Returns ALL study types (interventional + observational)"
echo ""
echo "2. RCT-FOCUSED (interventional studies only):"
echo "   query.cond=<condition>&filter.advanced=AREA[StudyType]INTERVENTIONAL"
echo "   Reduces results by ~20-30% while keeping all RCTs"
echo ""
echo "3. COMPLETED RCTS (likely published):"
echo "   query.cond=<condition>&filter.advanced=AREA[StudyType]INTERVENTIONAL"
echo "   &filter.overallStatus=COMPLETED"
echo "   Further reduces to ~30-50% of all studies"
echo ""
echo "4. PRECISION SEARCH (term + randomized):"
echo "   query.term=<condition> randomized"
echo "   Most restrictive - use for validation, not main search"
echo ""

echo "Results saved to: $RESULTS"
echo ""
echo "=== Validation Complete ==="
