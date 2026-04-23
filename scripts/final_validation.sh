#!/bin/bash
# sentinel:skip-file — hardcoded paths are fixture/registry/audit-narrative data for this repo's research workflow, not portable application configuration. Same pattern as push_all_repos.py and E156 workbook files.
# CT.gov Search Strategy Final Validation
# Direct API calls to CT.gov (not through worker)

echo "======================================================================"
echo "CT.gov Search Strategy Validation - Direct API"
echo "======================================================================"
echo ""

OUTPUT_DIR="C:/Users/user/Downloads/ctgov-search-strategies/output"
RESULTS="$OUTPUT_DIR/final_validation.csv"

echo "condition,strategy,total_count" > "$RESULTS"

# Function to search directly
search_direct() {
    local cond="$1"
    local strategy="$2"
    local extra="$3"

    local url="https://clinicaltrials.gov/api/v2/studies?query.cond=${cond}&countTotal=true&pageSize=1${extra}"

    local response=$(curl -s --max-time 30 "$url" 2>/dev/null)

    # Extract totalCount - it's at the start of JSON
    local count=$(echo "$response" | sed 's/.*"totalCount":\([0-9]*\).*/\1/' | head -1)

    # Validate it's a number
    if [[ "$count" =~ ^[0-9]+$ ]]; then
        echo "$cond,$strategy,$count" >> "$RESULTS"
        printf "  %-30s %10s results\n" "$strategy" "$count"
    else
        echo "$cond,$strategy,ERROR" >> "$RESULTS"
        printf "  %-30s %10s\n" "$strategy" "ERROR"
    fi
}

# Test conditions
CONDITIONS=("diabetes" "hypertension" "cancer" "asthma" "stroke" "depression" "heart%20failure" "covid-19")

for cond in "${CONDITIONS[@]}"; do
    echo ""
    display_cond=$(echo "$cond" | sed 's/%20/ /g')
    echo "CONDITION: $display_cond"
    echo "----------------------------------------"

    # Strategy 1: Condition only (all study types)
    search_direct "$cond" "cond_all_types" ""
    sleep 0.5

    # Strategy 2: Condition + Interventional
    search_direct "$cond" "cond_interventional" "&filter.studyType=INTERVENTIONAL"
    sleep 0.5

    # Strategy 3: Condition + Completed
    search_direct "$cond" "cond_completed" "&filter.overallStatus=COMPLETED"
    sleep 0.5

    # Strategy 4: Condition + Interventional + Completed
    search_direct "$cond" "cond_interv_completed" "&filter.studyType=INTERVENTIONAL&filter.overallStatus=COMPLETED"
    sleep 0.5

    # Strategy 5: Condition + Has Results
    search_direct "$cond" "cond_has_results" "&filter.resultsReported=true"
    sleep 0.5
done

echo ""
echo "======================================================================"
echo "SUMMARY ANALYSIS"
echo "======================================================================"
echo ""

echo "BY STRATEGY (average across conditions):"
echo "-----------------------------------------"
awk -F',' 'NR>1 && $3!="ERROR" {
    sum[$2]+=$3
    count[$2]++
}
END {
    for(s in sum)
        printf "%-30s %10.0f avg\n", s, sum[s]/count[s]
}' "$RESULTS" | sort -t'g' -k2 -rn

echo ""
echo "BY CONDITION (cond_all_types strategy):"
echo "----------------------------------------"
grep "cond_all_types" "$RESULTS" | awk -F',' '$3!="ERROR" {printf "%-20s %10s\n", $1, $3}' | sort -t' ' -k2 -rn

echo ""
echo "======================================================================"
echo "FILTER EFFECTIVENESS"
echo "======================================================================"

# Calculate reductions
echo ""
for cond in "${CONDITIONS[@]}"; do
    display_cond=$(echo "$cond" | sed 's/%20/ /g')
    all=$(grep "^${cond},cond_all_types" "$RESULTS" | cut -d',' -f3)
    interv=$(grep "^${cond},cond_interventional" "$RESULTS" | cut -d',' -f3)
    completed=$(grep "^${cond},cond_completed" "$RESULTS" | cut -d',' -f3)
    both=$(grep "^${cond},cond_interv_completed" "$RESULTS" | cut -d',' -f3)

    if [[ "$all" =~ ^[0-9]+$ ]] && [ "$all" -gt 0 ]; then
        echo "$display_cond:"

        if [[ "$interv" =~ ^[0-9]+$ ]]; then
            pct=$(awk "BEGIN {printf \"%.1f\", ($interv/$all)*100}")
            echo "  + Interventional filter: $interv ($pct% of all)"
        fi

        if [[ "$completed" =~ ^[0-9]+$ ]]; then
            pct=$(awk "BEGIN {printf \"%.1f\", ($completed/$all)*100}")
            echo "  + Completed filter:      $completed ($pct% of all)"
        fi

        if [[ "$both" =~ ^[0-9]+$ ]]; then
            pct=$(awk "BEGIN {printf \"%.1f\", ($both/$all)*100}")
            echo "  + Both filters:          $both ($pct% of all)"
        fi
        echo ""
    fi
done

echo "======================================================================"
echo "RECOMMENDATIONS FOR CT.GOV SEARCHES"
echo "======================================================================"
echo ""
echo "SEARCH STRATEGY RANKING (by precision/recall tradeoff):"
echo ""
echo "1. HIGHEST RECALL (find everything):"
echo "   query.cond=<condition>"
echo "   Use when: You cannot afford to miss any study"
echo ""
echo "2. BALANCED (RCTs only):"
echo "   query.cond=<condition>&filter.studyType=INTERVENTIONAL"
echo "   Use when: Looking for intervention studies (RCTs + single-arm)"
echo ""
echo "3. FOCUSED (completed RCTs):"
echo "   query.cond=<condition>&filter.studyType=INTERVENTIONAL&filter.overallStatus=COMPLETED"
echo "   Use when: Want studies that may have published results"
echo ""
echo "4. MOST PRECISE (with results):"
echo "   query.cond=<condition>&filter.resultsReported=true"
echo "   Use when: Only want studies with posted results on CT.gov"
echo ""
echo "RECOMMENDED SYSTEMATIC REVIEW WORKFLOW:"
echo "1. Run search with filter.studyType=INTERVENTIONAL"
echo "2. Export NCT IDs"
echo "3. Cross-reference with your included studies"
echo "4. Calculate recall (what % of your included studies were found)"
echo ""
echo "Results saved to: $RESULTS"
echo ""
echo "=== Validation Complete ==="
