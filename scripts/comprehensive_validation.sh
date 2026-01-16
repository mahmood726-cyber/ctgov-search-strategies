#!/bin/bash
# CT.gov Search Strategy Comprehensive Validation
# Tests 10 search strategies across multiple conditions
# Direct API calls with proper syntax

echo "======================================================================"
echo "CT.gov Search Strategy Comprehensive Validation"
echo "Based on Cochrane Guidance & API v2 Best Practices"
echo "======================================================================"
echo ""

OUTPUT_DIR="C:/Users/user/Downloads/ctgov-search-strategies/output"
RESULTS="$OUTPUT_DIR/comprehensive_results.csv"
DETAILED="$OUTPUT_DIR/detailed_analysis.txt"

# Initialize output files
echo "condition,strategy,strategy_name,total_count,query_url" > "$RESULTS"
echo "" > "$DETAILED"
echo "CT.gov Search Strategy Detailed Analysis" >> "$DETAILED"
echo "Generated: $(date)" >> "$DETAILED"
echo "======================================" >> "$DETAILED"

# Function to search CT.gov API directly
search_ctgov() {
    local cond="$1"
    local strategy_id="$2"
    local strategy_name="$3"
    local query="$4"

    local url="https://clinicaltrials.gov/api/v2/studies?${query}&countTotal=true&pageSize=1"

    local response=$(curl -s --max-time 45 "$url" 2>/dev/null)
    local count=$(echo "$response" | sed 's/.*"totalCount":\([0-9]*\).*/\1/' | head -1)

    if [[ "$count" =~ ^[0-9]+$ ]]; then
        echo "$cond,$strategy_id,$strategy_name,$count,$url" >> "$RESULTS"
        printf "  %-3s %-35s %10s\n" "$strategy_id" "$strategy_name" "$count"
    else
        echo "$cond,$strategy_id,$strategy_name,ERROR,$url" >> "$RESULTS"
        printf "  %-3s %-35s %10s\n" "$strategy_id" "$strategy_name" "ERROR"
    fi
}

# Test conditions (common systematic review topics)
declare -A CONDITIONS
CONDITIONS["diabetes"]="diabetes"
CONDITIONS["hypertension"]="hypertension"
CONDITIONS["depression"]="depression"
CONDITIONS["breast_cancer"]="breast cancer"
CONDITIONS["heart_failure"]="heart failure"
CONDITIONS["stroke"]="stroke"

# URL encode function
urlencode() {
    local string="$1"
    echo "$string" | sed 's/ /%20/g' | sed 's/\[/%5B/g' | sed 's/\]/%5D/g' | sed 's/(/%28/g' | sed 's/)/%29/g'
}

for cond_key in "${!CONDITIONS[@]}"; do
    cond="${CONDITIONS[$cond_key]}"
    cond_encoded=$(urlencode "$cond")

    echo ""
    echo "======================================================================"
    echo "CONDITION: $cond"
    echo "======================================================================"

    # Strategy 1: Maximum Recall - Condition Only (Cochrane Recommended)
    search_ctgov "$cond_key" "S1" "Condition only (max recall)" "query.cond=${cond_encoded}"
    sleep 0.5

    # Strategy 2: Condition + Interventional (AREA syntax)
    area_interv=$(urlencode "AREA[StudyType]INTERVENTIONAL")
    search_ctgov "$cond_key" "S2" "Interventional studies" "query.cond=${cond_encoded}&query.term=${area_interv}"
    sleep 0.5

    # Strategy 3: Condition + Randomized allocation only
    area_rand=$(urlencode "AREA[DesignAllocation]RANDOMIZED")
    search_ctgov "$cond_key" "S3" "Randomized allocation only" "query.cond=${cond_encoded}&query.term=${area_rand}"
    sleep 0.5

    # Strategy 4: Condition + Phase 3/4
    area_phase=$(urlencode "AREA[Phase](PHASE3 OR PHASE4)")
    search_ctgov "$cond_key" "S4" "Phase 3/4 studies" "query.cond=${cond_encoded}&query.term=${area_phase}"
    sleep 0.5

    # Strategy 5: Condition + Has Posted Results
    area_results=$(urlencode "AREA[ResultsFirstPostDate]RANGE[MIN,MAX]")
    search_ctgov "$cond_key" "S5" "Has posted results" "query.cond=${cond_encoded}&query.term=${area_results}"
    sleep 0.5

    # Strategy 6: Condition + Completed status
    search_ctgov "$cond_key" "S6" "Completed status" "query.cond=${cond_encoded}&filter.overallStatus=COMPLETED"
    sleep 0.5

    # Strategy 7: Interventional + Completed
    search_ctgov "$cond_key" "S7" "Interventional + Completed" "query.cond=${cond_encoded}&query.term=${area_interv}&filter.overallStatus=COMPLETED"
    sleep 0.5

    # Strategy 8: Randomized + Phase 3/4 + Completed
    area_rand_phase=$(urlencode "AREA[DesignAllocation]RANDOMIZED AND AREA[Phase](PHASE3 OR PHASE4)")
    search_ctgov "$cond_key" "S8" "RCT + Phase3/4 + Completed" "query.cond=${cond_encoded}&query.term=${area_rand_phase}&filter.overallStatus=COMPLETED"
    sleep 0.5

    # Strategy 9: Full-text with RCT keywords
    term_rct=$(urlencode "${cond} AND randomized AND controlled")
    search_ctgov "$cond_key" "S9" "Full-text RCT keywords" "query.term=${term_rct}"
    sleep 0.5

    # Strategy 10: Treatment purpose + Randomized
    area_treatment=$(urlencode "AREA[DesignAllocation]RANDOMIZED AND AREA[DesignPrimaryPurpose]TREATMENT")
    search_ctgov "$cond_key" "S10" "Treatment RCTs only" "query.cond=${cond_encoded}&query.term=${area_treatment}"
    sleep 0.5

done

echo ""
echo "======================================================================"
echo "SUMMARY ANALYSIS"
echo "======================================================================"
echo ""

# Calculate averages by strategy
echo "AVERAGE RESULTS BY STRATEGY:"
echo "----------------------------"
awk -F',' 'NR>1 && $4!="ERROR" && $4 ~ /^[0-9]+$/ {
    sum[$2]+=$4
    count[$2]++
    name[$2]=$3
}
END {
    for(s in sum) {
        avg = sum[s]/count[s]
        printf "%-4s %-35s %10.0f avg\n", s, name[s], avg
    }
}' "$RESULTS" | sort

echo ""
echo "FILTER REDUCTION ANALYSIS (vs S1 baseline):"
echo "--------------------------------------------"

# Calculate reduction for each condition
for cond_key in "${!CONDITIONS[@]}"; do
    baseline=$(grep "^${cond_key},S1," "$RESULTS" | cut -d',' -f4)

    if [[ "$baseline" =~ ^[0-9]+$ ]] && [ "$baseline" -gt 0 ]; then
        echo ""
        echo "${CONDITIONS[$cond_key]}:"

        for strat in S2 S3 S4 S5 S6 S7 S8 S9 S10; do
            count=$(grep "^${cond_key},${strat}," "$RESULTS" | cut -d',' -f4)
            name=$(grep "^${cond_key},${strat}," "$RESULTS" | cut -d',' -f3)

            if [[ "$count" =~ ^[0-9]+$ ]]; then
                pct=$(awk "BEGIN {printf \"%.1f\", ($count/$baseline)*100}")
                printf "  %-4s %-30s %6s (%5s%% of baseline)\n" "$strat" "$name" "$count" "$pct"
            fi
        done
    fi
done

echo ""
echo "======================================================================"
echo "STRATEGY RECOMMENDATIONS"
echo "======================================================================"
echo ""

cat << 'EOF'
BASED ON COCHRANE GUIDANCE AND EMPIRICAL TESTING:

FOR MAXIMUM SENSITIVITY (Systematic Reviews):
---------------------------------------------
USE: S1 (Condition only) - query.cond=<condition>
WHY: Cochrane recommends avoiding filters to maximize recall
     Single-concept searches have highest sensitivity

FOR FINDING RCTs SPECIFICALLY:
------------------------------
USE: S3 (Randomized allocation) - AREA[DesignAllocation]RANDOMIZED
WHY: More precise than StudyType filter
     Excludes single-arm interventional studies

FOR LIKELY PUBLISHED TRIALS:
----------------------------
USE: S7 (Interventional + Completed)
WHY: Completed trials more likely to have publications
     Maintains reasonable recall

FOR VALIDATION/CONFIRMATION:
---------------------------
USE: S8 (RCT + Phase3/4 + Completed)
WHY: Highest quality trials
     Good for confirming specific studies exist

RECOMMENDED WORKFLOW:
--------------------
1. Start with S1 (maximum recall) - capture everything
2. Export NCT IDs
3. For sensitivity analysis: also run S3 or S9
4. De-duplicate across searches
5. Screen results

API QUERY PATTERNS:
------------------
Basic:     query.cond=<condition>
RCTs:      query.cond=<condition>&query.term=AREA[DesignAllocation]RANDOMIZED
Completed: query.cond=<condition>&filter.overallStatus=COMPLETED
Combined:  query.cond=<condition>&query.term=AREA[StudyType]INTERVENTIONAL AND AREA[Phase](PHASE3 OR PHASE4)
EOF

echo ""
echo "Results saved to: $RESULTS"
echo ""
echo "=== Comprehensive Validation Complete ==="
