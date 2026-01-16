/**
 * CT.gov Search Strategy Module
 * Uses Cloudflare Worker proxy to access ClinicalTrials.gov API v2
 */

const WORKER_URL = 'https://restless-term-5510.mahmood726.workers.dev/';
const CTGOV_API = 'https://clinicaltrials.gov/api/v2/studies';

/**
 * Build CT.gov API URL with search parameters
 */
function buildSearchUrl(params) {
    const url = new URL(CTGOV_API);

    // Add search parameters
    if (params.condition) url.searchParams.set('query.cond', params.condition);
    if (params.intervention) url.searchParams.set('query.intr', params.intervention);
    if (params.term) url.searchParams.set('query.term', params.term);
    if (params.title) url.searchParams.set('query.titles', params.title);
    if (params.outcome) url.searchParams.set('query.outc', params.outcome);
    if (params.sponsor) url.searchParams.set('query.spons', params.sponsor);
    if (params.location) url.searchParams.set('query.locn', params.location);

    // Filters
    if (params.studyType) url.searchParams.set('filter.studyType', params.studyType);
    if (params.status) url.searchParams.set('filter.overallStatus', params.status);
    if (params.phase) url.searchParams.set('filter.phase', params.phase);

    // Pagination
    url.searchParams.set('pageSize', params.pageSize || 100);
    if (params.pageToken) url.searchParams.set('pageToken', params.pageToken);

    // Fields to return
    url.searchParams.set('fields', 'NCTId|BriefTitle|Condition|InterventionName|Phase|OverallStatus|StartDate|CompletionDate|EnrollmentCount|StudyType');

    return url.toString();
}

/**
 * Search CT.gov via worker proxy
 */
async function searchCtGov(params) {
    const ctgovUrl = buildSearchUrl(params);
    const proxyUrl = `${WORKER_URL}?url=${encodeURIComponent(ctgovUrl)}`;

    try {
        const response = await fetch(proxyUrl);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Search error:', error);
        throw error;
    }
}

/**
 * Extract relevant data from API response
 */
function parseSearchResults(data) {
    if (!data.studies) return { studies: [], totalCount: 0 };

    const studies = data.studies.map(study => {
        const id = study.protocolSection?.identificationModule;
        const status = study.protocolSection?.statusModule;
        const design = study.protocolSection?.designModule;
        const conditions = study.protocolSection?.conditionsModule;
        const interventions = study.protocolSection?.armsInterventionsModule;

        return {
            nctId: id?.nctId || '',
            title: id?.briefTitle || '',
            officialTitle: id?.officialTitle || '',
            conditions: conditions?.conditions || [],
            interventions: interventions?.interventions?.map(i => i.name) || [],
            phase: design?.phases || [],
            studyType: design?.studyType || '',
            status: status?.overallStatus || '',
            startDate: status?.startDateStruct?.date || '',
            completionDate: status?.completionDateStruct?.date || '',
            enrollment: design?.enrollmentInfo?.count || 0
        };
    });

    return {
        studies,
        totalCount: data.totalCount || studies.length,
        nextPageToken: data.nextPageToken
    };
}

/**
 * Search strategies to test
 */
const SEARCH_STRATEGIES = {
    // Strategy 1: Condition only
    conditionOnly: (condition) => ({
        condition,
        studyType: 'INTERVENTIONAL'
    }),

    // Strategy 2: Condition + completed status
    conditionCompleted: (condition) => ({
        condition,
        studyType: 'INTERVENTIONAL',
        status: 'COMPLETED'
    }),

    // Strategy 3: Condition + intervention
    conditionIntervention: (condition, intervention) => ({
        condition,
        intervention,
        studyType: 'INTERVENTIONAL'
    }),

    // Strategy 4: Full text search
    fullText: (term) => ({
        term,
        studyType: 'INTERVENTIONAL'
    }),

    // Strategy 5: Title search
    titleSearch: (title) => ({
        title,
        studyType: 'INTERVENTIONAL'
    }),

    // Strategy 6: Combined condition + outcome
    conditionOutcome: (condition, outcome) => ({
        condition,
        outcome,
        studyType: 'INTERVENTIONAL'
    }),

    // Strategy 7: Broad OR search using full text
    broadSearch: (terms) => ({
        term: terms.join(' OR '),
        studyType: 'INTERVENTIONAL'
    }),

    // Strategy 8: Narrow AND search
    narrowSearch: (terms) => ({
        term: terms.join(' AND '),
        studyType: 'INTERVENTIONAL'
    })
};

/**
 * Run a search and calculate metrics
 */
async function evaluateSearch(params, knownStudies = []) {
    const startTime = Date.now();
    const results = await searchCtGov(params);
    const parsed = parseSearchResults(results);
    const duration = Date.now() - startTime;

    // Calculate sensitivity (if known studies provided)
    let sensitivity = null;
    let foundStudies = [];
    if (knownStudies.length > 0) {
        // Try to match by title keywords
        foundStudies = knownStudies.filter(known => {
            const knownLower = known.toLowerCase();
            return parsed.studies.some(found =>
                found.title.toLowerCase().includes(knownLower) ||
                found.officialTitle?.toLowerCase().includes(knownLower)
            );
        });
        sensitivity = foundStudies.length / knownStudies.length;
    }

    return {
        totalFound: parsed.totalCount,
        studiesReturned: parsed.studies.length,
        duration,
        sensitivity,
        foundStudies,
        studies: parsed.studies,
        nextPageToken: parsed.nextPageToken
    };
}

/**
 * Compare multiple search strategies
 */
async function compareStrategies(strategies, knownStudies = []) {
    const results = [];

    for (const [name, params] of Object.entries(strategies)) {
        try {
            const evaluation = await evaluateSearch(params, knownStudies);
            results.push({
                strategy: name,
                ...evaluation
            });
        } catch (error) {
            results.push({
                strategy: name,
                error: error.message
            });
        }

        // Rate limiting
        await new Promise(resolve => setTimeout(resolve, 500));
    }

    return results;
}

// Export for use in HTML
if (typeof window !== 'undefined') {
    window.CTGovSearch = {
        searchCtGov,
        parseSearchResults,
        evaluateSearch,
        compareStrategies,
        SEARCH_STRATEGIES,
        buildSearchUrl,
        WORKER_URL,
        CTGOV_API
    };
}

// Export for Node.js
if (typeof module !== 'undefined') {
    module.exports = {
        searchCtGov,
        parseSearchResults,
        evaluateSearch,
        compareStrategies,
        SEARCH_STRATEGIES,
        buildSearchUrl,
        WORKER_URL,
        CTGOV_API
    };
}
