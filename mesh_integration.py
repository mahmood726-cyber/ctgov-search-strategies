#!/usr/bin/env python3
"""
MeSH/SNOMED Integration Module for CT.gov Search Strategies

Provides comprehensive medical terminology expansion using:
- NLM MeSH API for Medical Subject Headings
- SNOMED CT cross-references
- MeSH tree hierarchy expansion
- Auto-suggestion of related terms

This module enables more comprehensive searches by expanding condition
names to include related MeSH terms, synonyms, and SNOMED CT concepts.

References:
    - NLM MeSH API: https://meshb.nlm.nih.gov/api
    - SNOMED CT: https://www.snomed.org/
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Final, List, Optional, Set, Tuple, TypedDict

import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API Configuration
MESH_API_BASE: Final[str] = "https://id.nlm.nih.gov/mesh"
MESH_SPARQL_ENDPOINT: Final[str] = "https://id.nlm.nih.gov/mesh/sparql"
MESH_LOOKUP_API: Final[str] = "https://meshb.nlm.nih.gov/api/search/mesh"
UMLS_API_BASE: Final[str] = "https://uts-ws.nlm.nih.gov/rest"

# Rate limiting
RATE_LIMIT_DELAY: Final[float] = 0.25  # 250ms between requests
MAX_RETRIES: Final[int] = 3
RETRY_DELAYS: Final[Tuple[float, ...]] = (1.0, 2.0, 4.0)  # Exponential backoff

# Cache configuration
CACHE_DIR: Final[Path] = Path(__file__).resolve().parent / "data" / "mesh_cache"
CACHE_EXPIRY_DAYS: Final[int] = 30


class MeSHTermDict(TypedDict, total=False):
    """TypedDict for MeSH term information."""
    ui: str  # MeSH Unique Identifier (e.g., D003920)
    name: str  # Preferred term name
    tree_numbers: List[str]  # MeSH tree numbers (e.g., C18.452.394.750)
    synonyms: List[str]  # Entry terms / synonyms
    scope_note: str  # Definition/scope note
    parent_terms: List[str]  # Broader terms
    child_terms: List[str]  # Narrower terms
    related_terms: List[str]  # See Also references


class SnomedConceptDict(TypedDict, total=False):
    """TypedDict for SNOMED CT concept information."""
    concept_id: str  # SNOMED CT concept ID
    preferred_term: str  # Fully specified name
    synonyms: List[str]  # Acceptable synonyms
    semantic_type: str  # Semantic type (disorder, finding, etc.)


class MeSHExpansionResult(TypedDict):
    """TypedDict for MeSH expansion result."""
    original_term: str
    mesh_terms: List[MeSHTermDict]
    all_synonyms: List[str]
    tree_expanded_terms: List[str]
    snomed_mappings: List[SnomedConceptDict]
    query_terms: List[str]  # Final list of terms for search


@dataclass
class MeSHTerm:
    """Represents a MeSH term with full metadata."""
    ui: str
    name: str
    tree_numbers: List[str] = field(default_factory=list)
    synonyms: List[str] = field(default_factory=list)
    scope_note: str = ""
    parent_uis: List[str] = field(default_factory=list)
    child_uis: List[str] = field(default_factory=list)
    related_uis: List[str] = field(default_factory=list)

    def to_dict(self) -> MeSHTermDict:
        """Convert to dictionary representation."""
        return {
            'ui': self.ui,
            'name': self.name,
            'tree_numbers': self.tree_numbers,
            'synonyms': self.synonyms,
            'scope_note': self.scope_note
        }


class MeSHIntegrationError(Exception):
    """Exception raised for MeSH integration errors."""
    pass


class MeSHClient:
    """
    Client for interacting with NLM MeSH API.

    Provides methods to:
    - Look up MeSH terms by name
    - Get term synonyms and entry terms
    - Navigate the MeSH tree hierarchy
    - Expand terms to include related concepts

    Example:
        >>> client = MeSHClient()
        >>> terms = client.search_mesh("diabetes mellitus")
        >>> for term in terms:
        ...     print(f"{term.ui}: {term.name}")
        D003920: Diabetes Mellitus

        >>> expansion = client.expand_term("diabetes")
        >>> print(f"Found {len(expansion['all_synonyms'])} synonyms")
    """

    def __init__(
        self,
        timeout: int = 30,
        cache_enabled: bool = True,
        user_agent: str = "CTGov-Search-Strategies/1.0"
    ) -> None:
        """
        Initialize the MeSH client.

        Args:
            timeout: Request timeout in seconds.
            cache_enabled: Whether to cache API responses.
            user_agent: User-Agent header for HTTP requests.
        """
        self.timeout = timeout
        self.cache_enabled = cache_enabled
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': user_agent,
            'Accept': 'application/json'
        })
        self._last_request_time: float = 0.0

        if cache_enabled:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _rate_limit(self) -> None:
        """Enforce rate limiting between API requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()

    def _make_request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        Make an HTTP request with retry logic and rate limiting.

        Args:
            url: The URL to request.
            params: Optional query parameters.
            retry_count: Current retry attempt number.

        Returns:
            JSON response as dictionary.

        Raises:
            MeSHIntegrationError: If request fails after all retries.
        """
        self._rate_limit()

        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if retry_count < MAX_RETRIES:
                delay = RETRY_DELAYS[retry_count]
                logger.warning(f"Request failed, retrying in {delay}s: {e}")
                time.sleep(delay)
                return self._make_request(url, params, retry_count + 1)
            raise MeSHIntegrationError(f"Request failed after {MAX_RETRIES} retries: {e}")

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get the cache file path for a given key."""
        safe_key = re.sub(r'[^\w\-]', '_', cache_key)[:100]
        return CACHE_DIR / f"{safe_key}.json"

    def _get_cached(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached data if valid."""
        if not self.cache_enabled:
            return None

        cache_path = self._get_cache_path(cache_key)
        if not cache_path.exists():
            return None

        try:
            data = json.loads(cache_path.read_text(encoding='utf-8'))
            # Check expiry
            cached_time = data.get('_cached_at', 0)
            if time.time() - cached_time > CACHE_EXPIRY_DAYS * 86400:
                return None
            return data.get('data')
        except Exception:
            return None

    def _set_cached(self, cache_key: str, data: Any) -> None:
        """Store data in cache."""
        if not self.cache_enabled:
            return

        cache_path = self._get_cache_path(cache_key)
        try:
            cache_data = {
                '_cached_at': time.time(),
                'data': data
            }
            cache_path.write_text(json.dumps(cache_data, indent=2), encoding='utf-8')
        except Exception as e:
            logger.warning(f"Failed to cache data: {e}")

    @lru_cache(maxsize=256)
    def search_mesh(self, query: str, limit: int = 10) -> List[MeSHTerm]:
        """
        Search for MeSH terms matching a query.

        Uses the MeSH Browser API to find terms by name or concept.

        Args:
            query: Search query (condition name, term, etc.)
            limit: Maximum number of results to return.

        Returns:
            List of MeSHTerm objects matching the query.

        Example:
            >>> terms = client.search_mesh("type 2 diabetes")
            >>> print(terms[0].name)
            Diabetes Mellitus, Type 2
        """
        cache_key = f"search_{query}_{limit}"
        cached = self._get_cached(cache_key)
        if cached:
            return [MeSHTerm(**t) for t in cached]

        url = f"{MESH_LOOKUP_API}"
        params = {
            'searchInField': 'term',
            'searchType': 'exactMatch',
            'searchMethod': 'contains',
            'q': query,
            'limit': limit,
            'year': 'current'
        }

        try:
            # Try exact match first
            data = self._make_request(url, params)
            results = data.get('hits', [])

            # If no exact matches, try broader search
            if not results:
                params['searchType'] = 'anyContains'
                data = self._make_request(url, params)
                results = data.get('hits', [])

            terms = []
            for hit in results[:limit]:
                resource = hit.get('resource', {})
                term = MeSHTerm(
                    ui=resource.get('dcterms:identifier', ''),
                    name=resource.get('rdfs:label', ''),
                    tree_numbers=resource.get('meshv:treeNumber', []),
                    synonyms=self._extract_synonyms(resource),
                    scope_note=resource.get('meshv:scopeNote', '')
                )
                terms.append(term)

            # Cache results
            self._set_cached(cache_key, [t.__dict__ for t in terms])

            return terms

        except MeSHIntegrationError as e:
            logger.error(f"MeSH search failed for '{query}': {e}")
            return []

    def _extract_synonyms(self, resource: Dict[str, Any]) -> List[str]:
        """Extract all synonyms/entry terms from a MeSH resource."""
        synonyms = []

        # Entry terms
        entry_terms = resource.get('meshv:term', [])
        if isinstance(entry_terms, list):
            for term in entry_terms:
                if isinstance(term, dict):
                    label = term.get('rdfs:label', '')
                    if label:
                        synonyms.append(label)
                elif isinstance(term, str):
                    synonyms.append(term)

        # Concept terms
        concepts = resource.get('meshv:concept', [])
        if isinstance(concepts, list):
            for concept in concepts:
                if isinstance(concept, dict):
                    terms = concept.get('meshv:term', [])
                    if isinstance(terms, list):
                        for t in terms:
                            if isinstance(t, dict):
                                label = t.get('rdfs:label', '')
                                if label:
                                    synonyms.append(label)

        return list(set(synonyms))

    def get_term_by_ui(self, ui: str) -> Optional[MeSHTerm]:
        """
        Retrieve a MeSH term by its unique identifier.

        Args:
            ui: MeSH Unique Identifier (e.g., D003920).

        Returns:
            MeSHTerm object or None if not found.
        """
        cache_key = f"term_{ui}"
        cached = self._get_cached(cache_key)
        if cached:
            return MeSHTerm(**cached)

        url = f"{MESH_API_BASE}/lookup/descriptor/{ui}"

        try:
            data = self._make_request(url)

            term = MeSHTerm(
                ui=data.get('@id', '').split('/')[-1],
                name=data.get('label', {}).get('@value', ''),
                tree_numbers=[tn.get('@value', '') for tn in data.get('treeNumber', [])],
                synonyms=[t.get('label', {}).get('@value', '')
                         for t in data.get('term', []) if t.get('label')],
                scope_note=data.get('scopeNote', {}).get('@value', '')
            )

            self._set_cached(cache_key, term.__dict__)
            return term

        except MeSHIntegrationError:
            return None

    def get_tree_children(self, tree_number: str) -> List[str]:
        """
        Get all child tree numbers for a given MeSH tree number.

        Args:
            tree_number: MeSH tree number (e.g., C18.452.394.750)

        Returns:
            List of child tree numbers.
        """
        cache_key = f"children_{tree_number}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        # Use SPARQL to find children
        sparql_query = f"""
        PREFIX meshv: <http://id.nlm.nih.gov/mesh/vocab#>
        PREFIX mesh: <http://id.nlm.nih.gov/mesh/>

        SELECT ?child WHERE {{
            ?child meshv:treeNumber ?tn .
            FILTER(STRSTARTS(?tn, "{tree_number}."))
        }}
        LIMIT 100
        """

        try:
            response = self.session.get(
                MESH_SPARQL_ENDPOINT,
                params={'query': sparql_query, 'format': 'json'},
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            children = [
                binding['child']['value'].split('/')[-1]
                for binding in data.get('results', {}).get('bindings', [])
            ]

            self._set_cached(cache_key, children)
            return children

        except Exception as e:
            logger.warning(f"Failed to get tree children for {tree_number}: {e}")
            return []

    def expand_term(
        self,
        term: str,
        include_children: bool = True,
        include_parents: bool = False,
        max_depth: int = 2
    ) -> MeSHExpansionResult:
        """
        Expand a medical term to include all related MeSH concepts.

        This is the primary method for comprehensive term expansion,
        returning all synonyms, related terms, and optionally child/parent
        concepts from the MeSH hierarchy.

        Args:
            term: The medical term to expand.
            include_children: Whether to include narrower terms from MeSH tree.
            include_parents: Whether to include broader terms from MeSH tree.
            max_depth: Maximum tree depth to traverse.

        Returns:
            MeSHExpansionResult with all expanded terms.

        Example:
            >>> result = client.expand_term("diabetes mellitus")
            >>> print(f"Original: {result['original_term']}")
            >>> print(f"Synonyms: {len(result['all_synonyms'])}")
            >>> print(f"Query terms: {result['query_terms'][:5]}")
        """
        result: MeSHExpansionResult = {
            'original_term': term,
            'mesh_terms': [],
            'all_synonyms': [],
            'tree_expanded_terms': [],
            'snomed_mappings': [],
            'query_terms': [term]
        }

        # Search for matching MeSH terms
        mesh_terms = self.search_mesh(term, limit=5)

        if not mesh_terms:
            logger.info(f"No MeSH terms found for '{term}'")
            return result

        result['mesh_terms'] = [t.to_dict() for t in mesh_terms]

        # Collect all synonyms
        all_synonyms: Set[str] = {term.lower()}

        for mesh_term in mesh_terms:
            # Add the preferred name
            all_synonyms.add(mesh_term.name.lower())

            # Add all synonyms/entry terms
            for syn in mesh_term.synonyms:
                all_synonyms.add(syn.lower())

            # Expand tree hierarchy if requested
            if include_children and mesh_term.tree_numbers:
                for tree_num in mesh_term.tree_numbers[:3]:  # Limit tree expansions
                    children = self.get_tree_children(tree_num)
                    for child_ui in children[:10]:  # Limit children per tree
                        child_term = self.get_term_by_ui(child_ui)
                        if child_term:
                            result['tree_expanded_terms'].append(child_term.name)
                            all_synonyms.add(child_term.name.lower())

        result['all_synonyms'] = sorted(list(all_synonyms - {term.lower()}))
        result['query_terms'] = [term] + result['all_synonyms']

        return result

    def get_search_query(
        self,
        term: str,
        expand: bool = True,
        max_terms: int = 20
    ) -> str:
        """
        Generate an optimized CT.gov search query with MeSH expansion.

        Args:
            term: The medical term to search.
            expand: Whether to expand using MeSH.
            max_terms: Maximum number of terms in the OR query.

        Returns:
            Search query string for CT.gov API.

        Example:
            >>> query = client.get_search_query("diabetes")
            >>> print(query)
            "diabetes" OR "diabetes mellitus" OR "type 2 diabetes" ...
        """
        if not expand:
            return f'"{term}"'

        expansion = self.expand_term(term, include_children=True)
        terms = expansion['query_terms'][:max_terms]

        # Build OR query with quoted terms
        quoted_terms = [f'"{t}"' for t in terms]
        return ' OR '.join(quoted_terms)

    def suggest_terms(self, partial: str, limit: int = 10) -> List[str]:
        """
        Get auto-complete suggestions for a partial term.

        Useful for building search interfaces with term suggestions.

        Args:
            partial: Partial term input.
            limit: Maximum number of suggestions.

        Returns:
            List of suggested MeSH term names.
        """
        if len(partial) < 2:
            return []

        terms = self.search_mesh(partial, limit=limit)
        suggestions = []

        for term in terms:
            suggestions.append(term.name)
            # Add top synonyms
            for syn in term.synonyms[:2]:
                if syn.lower() != term.name.lower():
                    suggestions.append(syn)

        return list(dict.fromkeys(suggestions))[:limit]  # Deduplicate preserving order


class SnomedClient:
    """
    Client for SNOMED CT cross-references via UMLS.

    Note: Requires UMLS API key for full functionality.
    Falls back to MeSH-SNOMED mappings when API key not available.
    """

    # Common MeSH to SNOMED CT mappings for clinical trials
    MESH_SNOMED_MAPPINGS: Final[Dict[str, List[str]]] = {
        'D003920': ['73211009'],  # Diabetes Mellitus -> Diabetes mellitus
        'D006333': ['56265001'],  # Heart Diseases -> Heart disease
        'D009369': ['363346000'],  # Neoplasms -> Malignant neoplastic disease
        'D001249': ['195967001'],  # Asthma -> Asthma
        'D006973': ['38341003'],  # Hypertension -> Hypertensive disorder
        'D020521': ['230690007'],  # Stroke -> Cerebrovascular accident
        'D003866': ['35489007'],  # Depression -> Depressive disorder
        'D000544': ['26929004'],  # Alzheimer Disease -> Alzheimer's disease
        'D010300': ['49049000'],  # Parkinson Disease -> Parkinson's disease
        'D001943': ['254837009'],  # Breast Neoplasms -> Malignant tumor of breast
    }

    def __init__(self, api_key: Optional[str] = None) -> None:
        """
        Initialize SNOMED client.

        Args:
            api_key: Optional UMLS API key for full SNOMED access.
        """
        self.api_key = api_key
        self.session = requests.Session()

    def get_snomed_for_mesh(self, mesh_ui: str) -> List[SnomedConceptDict]:
        """
        Get SNOMED CT concepts mapped to a MeSH descriptor.

        Args:
            mesh_ui: MeSH Unique Identifier.

        Returns:
            List of SNOMED CT concepts.
        """
        # Use local mappings
        snomed_ids = self.MESH_SNOMED_MAPPINGS.get(mesh_ui, [])

        concepts = []
        for snomed_id in snomed_ids:
            concepts.append({
                'concept_id': snomed_id,
                'preferred_term': f'SNOMED:{snomed_id}',
                'synonyms': [],
                'semantic_type': 'clinical finding'
            })

        return concepts


class MeSHExpander:
    """
    High-level interface for MeSH-based search term expansion.

    Combines MeSH and SNOMED lookups to provide comprehensive
    term expansion for systematic review searches.

    Example:
        >>> expander = MeSHExpander()
        >>> result = expander.expand_condition("type 2 diabetes")
        >>> print(f"Expanded to {len(result['query_terms'])} terms")
    """

    def __init__(
        self,
        mesh_client: Optional[MeSHClient] = None,
        snomed_client: Optional[SnomedClient] = None
    ) -> None:
        """
        Initialize the MeSH expander.

        Args:
            mesh_client: Optional pre-configured MeSH client.
            snomed_client: Optional pre-configured SNOMED client.
        """
        self.mesh_client = mesh_client or MeSHClient()
        self.snomed_client = snomed_client or SnomedClient()

    def expand_condition(
        self,
        condition: str,
        include_snomed: bool = True,
        max_terms: int = 25
    ) -> MeSHExpansionResult:
        """
        Fully expand a condition name using MeSH and SNOMED.

        Args:
            condition: Medical condition name.
            include_snomed: Whether to include SNOMED mappings.
            max_terms: Maximum total terms to include.

        Returns:
            Complete expansion result with all related terms.
        """
        # Get MeSH expansion
        result = self.mesh_client.expand_term(condition)

        # Add SNOMED mappings
        if include_snomed and result['mesh_terms']:
            for mesh_term in result['mesh_terms'][:3]:
                mesh_ui = mesh_term.get('ui', '')
                if mesh_ui:
                    snomed_concepts = self.snomed_client.get_snomed_for_mesh(mesh_ui)
                    result['snomed_mappings'].extend(snomed_concepts)

        # Limit total terms
        result['query_terms'] = result['query_terms'][:max_terms]

        return result

    def get_optimized_query(
        self,
        condition: str,
        strategy: str = 'balanced'
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Generate an optimized search query based on strategy.

        Args:
            condition: Medical condition to search.
            strategy: Query strategy:
                - 'sensitive': Maximum recall, more terms
                - 'specific': Higher precision, fewer terms
                - 'balanced': Balance of recall and precision

        Returns:
            Tuple of (query_string, metadata_dict)
        """
        expansion = self.expand_condition(condition)

        if strategy == 'sensitive':
            terms = expansion['query_terms'][:30]
        elif strategy == 'specific':
            # Only use main MeSH terms
            terms = [condition]
            if expansion['mesh_terms']:
                terms.append(expansion['mesh_terms'][0].get('name', ''))
        else:  # balanced
            terms = expansion['query_terms'][:15]

        # Build query
        quoted = [f'"{t}"' for t in terms]
        query = ' OR '.join(quoted)

        metadata = {
            'original_condition': condition,
            'strategy': strategy,
            'num_terms': len(terms),
            'mesh_terms_found': len(expansion['mesh_terms']),
            'snomed_mappings': len(expansion['snomed_mappings'])
        }

        return query, metadata


def main() -> None:
    """Demo usage of the MeSH integration module."""
    print("=" * 70)
    print("  MeSH Integration Module - Demo")
    print("=" * 70)

    client = MeSHClient()
    expander = MeSHExpander(mesh_client=client)

    # Test conditions
    test_conditions = [
        "diabetes mellitus",
        "breast cancer",
        "hypertension",
        "heart failure",
        "covid-19"
    ]

    for condition in test_conditions:
        print(f"\n{'='*50}")
        print(f"Condition: {condition}")
        print("=" * 50)

        # Search MeSH
        terms = client.search_mesh(condition, limit=3)
        if terms:
            print(f"\nMeSH Terms Found ({len(terms)}):")
            for term in terms:
                print(f"  - {term.ui}: {term.name}")
                if term.synonyms:
                    print(f"    Synonyms: {', '.join(term.synonyms[:5])}")

        # Expand term
        expansion = expander.expand_condition(condition)
        print(f"\nExpansion Results:")
        print(f"  Total synonyms: {len(expansion['all_synonyms'])}")
        print(f"  Tree-expanded terms: {len(expansion['tree_expanded_terms'])}")
        print(f"  Query terms: {len(expansion['query_terms'])}")

        if expansion['all_synonyms']:
            print(f"\nTop synonyms: {', '.join(expansion['all_synonyms'][:8])}")

        # Generate query
        query, meta = expander.get_optimized_query(condition, strategy='balanced')
        print(f"\nOptimized Query ({meta['num_terms']} terms):")
        print(f"  {query[:200]}...")

    print("\n" + "=" * 70)
    print("  Demo complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
