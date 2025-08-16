import os
from typing import List, Dict, Any
from models import SearchResult
from services.image_processor import ImageProcessor

class SearchService:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.image_processor = ImageProcessor()
    
    async def hybrid_search(self, query: str, limit: int = 5) -> List[SearchResult]:
        """Perform intelligent hybrid search with visual content prioritization."""
        try:
            # Get all processed screenshots
            screenshots = self.db_manager.get_all_processed_screenshots()
            
            if not screenshots:
                return []
            
            # Create query embedding
            query_embedding = self.image_processor.create_embeddings(query)
            
            # Analyze query type and calculate scores
            scored_results = []
            query_analysis = self._analyze_query(query)
            
            for screenshot in screenshots:
                if not screenshot.get('text_embedding'):
                    continue
                
                score = self._calculate_relevance_score(
                    query, query_analysis, screenshot, query_embedding
                )
                
                if score > 0.1:  # Only include reasonably relevant results
                    result = SearchResult(
                        id=screenshot['id'],
                        filename=screenshot['filename'],
                        confidence_score=round(min(score * 100, 100), 1),
                        preview_url=f"/uploads/{os.path.basename(screenshot['file_path'])}",
                        ocr_text=screenshot.get('ocr_text', ''),
                        visual_description=screenshot.get('visual_description', ''),
                        matched_elements=self._find_matched_elements(query, query_analysis, screenshot)
                    )
                    scored_results.append((score, result))
            
            # Sort by relevance score (descending)
            scored_results.sort(key=lambda x: x[0], reverse=True)
            
            return [result for _, result in scored_results[:limit]]
        
        except Exception as e:
            print(f"Search error: {str(e)}")
            return []
    
    def _analyze_query(self, query: str) -> Dict[str, Any]:
        """Analyze query to determine search strategy and content type."""
        query_lower = query.lower()
        
        # Define content categories with keywords
        visual_keywords = {
            'nature': ['mountain', 'mountains', 'river', 'lake', 'forest', 'tree', 'landscape', 'nature', 'outdoor', 'scenery', 'beach', 'ocean', 'sea', 'sky', 'sunset', 'sunrise'],
            'urban': ['building', 'city', 'street', 'road', 'architecture', 'urban', 'downtown'],
            'people': ['person', 'people', 'man', 'woman', 'child', 'group', 'face'],
            'objects': ['car', 'vehicle', 'food', 'animal', 'bird', 'cat', 'dog'],
            'animated': ['character', 'characters', 'animated', 'animation', 'cartoon', 'anime', 'comic', 'mascot', 'emoji', 'avatar', 'bubu', 'chibi', 'cute', 'kawaii'],
            'general_visual': ['picture', 'photo', 'image', 'show', 'display', 'view']
        }
        
        ui_keywords = ['button', 'form', 'login', 'error', 'dialog', 'menu', 'interface', 'screen', 'app', 'website', 'page']
        
        # Special high-priority combinations
        auth_error_keywords = ['auth', 'authentication', 'login', 'password', 'sign in', 'credential', 'username']
        error_keywords = ['error', 'warning', 'alert', 'problem', 'issue', 'failed', 'fail']
        
        # Determine query type
        is_visual_query = False
        visual_categories = []
        
        for category, keywords in visual_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                is_visual_query = True
                visual_categories.append(category)
        
        is_ui_query = any(keyword in query_lower for keyword in ui_keywords)
        
        # Check for special high-priority combinations
        has_auth_terms = any(keyword in query_lower for keyword in auth_error_keywords)
        has_error_terms = any(keyword in query_lower for keyword in error_keywords)
        is_auth_error_query = has_auth_terms and has_error_terms
        
        # Extract specific content terms
        content_terms = []
        for category, keywords in visual_keywords.items():
            for keyword in keywords:
                if keyword in query_lower:
                    content_terms.append(keyword)
        
        return {
            'is_visual_query': is_visual_query,
            'is_ui_query': is_ui_query,
            'is_auth_error_query': is_auth_error_query,
            'has_auth_terms': has_auth_terms,
            'has_error_terms': has_error_terms,
            'visual_categories': visual_categories,
            'content_terms': content_terms,
            'query_lower': query_lower
        }
    
    def _calculate_relevance_score(self, query: str, query_analysis: Dict, screenshot: Dict, query_embedding: List) -> float:
        """Calculate comprehensive relevance score for a screenshot."""
        ocr_text = screenshot.get('ocr_text', '').lower()
        visual_description = screenshot.get('visual_description', '').lower()
        filename = screenshot.get('filename', '').lower()
        
        # Base similarity score
        base_score = self.image_processor.calculate_similarity(
            query_embedding, screenshot['text_embedding']
        )
        
        # Determine content type of screenshot
        screenshot_analysis = self._analyze_screenshot_content(ocr_text, visual_description, filename)
        
        # Calculate content relevance
        content_score = self._calculate_content_relevance(
            query_analysis, screenshot_analysis, ocr_text, visual_description, filename
        )
        
        # Calculate text matching score
        text_score = self._calculate_text_matching(
            query_analysis['query_lower'], ocr_text, visual_description
        )
        
        # Calculate filename matching score (NEW)
        filename_score = self._calculate_filename_matching(
            query_analysis['query_lower'], filename, query_analysis
        )
        
        # Weighted final score based on query type
        if query_analysis['is_auth_error_query']:
            # Special handling for auth+error queries - prioritize text content
            final_score = (
                base_score * 0.25 +          # Moderate weight for general similarity
                content_score * 0.2 +        # Lower weight for visual content
                text_score * 0.45 +          # High weight for text matching
                filename_score * 0.1         # Small weight for filename
            )
        elif query_analysis['is_visual_query']:
            # For visual queries, prioritize visual content and filename heavily
            final_score = (
                base_score * 0.15 +          # Lower weight for general similarity
                content_score * 0.5 +         # High weight for visual content relevance
                text_score * 0.15 +          # Lower weight for text matching
                filename_score * 0.2         # Higher weight for filename matching
            )
        else:
            # For text queries, balance all factors
            final_score = (
                base_score * 0.3 +
                content_score * 0.25 +
                text_score * 0.3 +
                filename_score * 0.15
            )
        
        return final_score
    
    def _analyze_screenshot_content(self, ocr_text: str, visual_description: str, filename: str = '') -> Dict[str, Any]:
        """Analyze what type of content is in the screenshot."""
        # UI/Interface indicators
        ui_indicators = ['button', 'form', 'login', 'error', 'dialog', 'menu', 'interface', 'click', 'text field', 'dropdown', 'checkbox', 'authentication', 'password', 'username', 'sign in', 'alert', 'warning']
        
        # Visual content indicators
        nature_indicators = ['mountain', 'river', 'lake', 'forest', 'tree', 'landscape', 'nature', 'outdoor', 'scenery', 'beach', 'ocean', 'sea', 'sky', 'sunset', 'sunrise', 'valley', 'peak', 'hill']
        urban_indicators = ['building', 'city', 'street', 'road', 'architecture', 'urban', 'downtown', 'skyscraper']
        people_indicators = ['person', 'people', 'man', 'woman', 'child', 'face', 'group', 'individual']
        animated_indicators = ['character', 'animated', 'cartoon', 'anime', 'comic', 'mascot', 'emoji', 'avatar', 'bubu', 'chibi', 'cute', 'kawaii', 'animation']
        
        combined_text = f"{ocr_text} {visual_description} {filename}"
        
        # Count indicators
        ui_count = sum(1 for indicator in ui_indicators if indicator in combined_text)
        nature_count = sum(1 for indicator in nature_indicators if indicator in combined_text)
        urban_count = sum(1 for indicator in urban_indicators if indicator in combined_text)
        people_count = sum(1 for indicator in people_indicators if indicator in combined_text)
        animated_count = sum(1 for indicator in animated_indicators if indicator in combined_text)
        
        # Determine primary content type
        is_primarily_ui = ui_count > 2 or len(ocr_text) > len(visual_description) * 2
        has_nature_content = nature_count > 0
        has_urban_content = urban_count > 0
        has_people_content = people_count > 0
        has_animated_content = animated_count > 0
        
        return {
            'is_primarily_ui': is_primarily_ui,
            'has_nature_content': has_nature_content,
            'has_urban_content': has_urban_content,
            'has_people_content': has_people_content,
            'has_animated_content': has_animated_content,
            'nature_count': nature_count,
            'ui_count': ui_count,
            'animated_count': animated_count,
            'text_to_visual_ratio': len(ocr_text) / max(len(visual_description), 1)
        }
    
    def _calculate_content_relevance(self, query_analysis: Dict, screenshot_analysis: Dict, ocr_text: str, visual_description: str, filename: str = '') -> float:
        """Calculate how well screenshot content matches query intent."""
        
        # Special handling for auth+error queries
        if query_analysis['is_auth_error_query']:
            score = 0.0
            combined_text = f"{ocr_text} {visual_description}".lower()
            
            # High reward for auth+error content
            if query_analysis['has_auth_terms'] and any(term in combined_text for term in ['auth', 'authentication', 'login', 'password', 'sign in']):
                score += 0.6
            if query_analysis['has_error_terms'] and any(term in combined_text for term in ['error', 'warning', 'alert', 'problem', 'failed']):
                score += 0.6
            
            # Heavy penalty for pure nature content when looking for auth errors
            if screenshot_analysis['has_nature_content'] and screenshot_analysis['ui_count'] == 0:
                score -= 0.8  # Much stronger penalty
            
            # Additional bonus if both auth and error terms are found
            if score > 1.0:
                score = 1.2  # Super high score for perfect matches
            
            return max(score, 0.0)
        
        elif query_analysis['is_visual_query']:
            # For visual queries, heavily penalize UI-heavy screenshots
            if screenshot_analysis['is_primarily_ui']:
                return 0.1  # Very low score for UI content on visual queries
            
            # Reward visual content matches
            score = 0.0
            
            # Check for specific content matches
            if 'nature' in query_analysis['visual_categories']:
                if screenshot_analysis['has_nature_content']:
                    score += 0.8
                    # Specific nature term bonuses
                    for term in query_analysis['content_terms']:
                        if term in visual_description:
                            score += 0.4
                        elif term in ocr_text:
                            score += 0.1  # Much lower for text matches
                else:
                    return 0.2  # Low score if no nature content for nature query
            
            if 'urban' in query_analysis['visual_categories']:
                if screenshot_analysis['has_urban_content']:
                    score += 0.8
                    for term in query_analysis['content_terms']:
                        if term in visual_description:
                            score += 0.4
            
            if 'people' in query_analysis['visual_categories']:
                if screenshot_analysis['has_people_content']:
                    score += 0.8
            
            # NEW: Handle animated content specifically
            if 'animated' in query_analysis['visual_categories']:
                if screenshot_analysis['has_animated_content']:
                    score += 0.9  # High score for animated content
                    # Extra bonus for specific animated terms in filename
                    for term in query_analysis['content_terms']:
                        if term in filename:
                            score += 0.3
                        elif term in visual_description:
                            score += 0.4
                else:
                    # Lower penalty for non-animated content when looking for animations
                    return 0.3
            
            return min(score, 1.0)
        
        else:
            # For non-visual queries, standard content matching
            return 0.5  # Neutral score
    
    def _calculate_text_matching(self, query_lower: str, ocr_text: str, visual_description: str) -> float:
        """Calculate text-based matching score."""
        score = 0.0
        
        # Exact query match
        if query_lower in visual_description:
            score += 0.8
        elif query_lower in ocr_text:
            score += 0.6
        
        # Word-by-word matching
        query_words = [w for w in query_lower.split() if len(w) > 2]
        if query_words:
            visual_matches = sum(1 for word in query_words if word in visual_description)
            ocr_matches = sum(1 for word in query_words if word in ocr_text)
            
            visual_ratio = visual_matches / len(query_words)
            ocr_ratio = ocr_matches / len(query_words)
            
            score += visual_ratio * 0.4 + ocr_ratio * 0.2
        
        return min(score, 1.0)
    
    def _find_matched_elements(self, query: str, query_analysis: Dict, screenshot: Dict) -> List[str]:
        """Find specific elements that match the query."""
        matched_elements = []
        
        ocr_text = screenshot.get('ocr_text', '').lower()
        visual_description = screenshot.get('visual_description', '').lower()
        query_lower = query_analysis['query_lower']
        
        # Exact matches
        if query_lower in visual_description:
            matched_elements.append(f"Exact visual match: '{query}'")
        if query_lower in ocr_text:
            matched_elements.append(f"Exact text match: '{query}'")
        
        # Content category matches
        for category in query_analysis['visual_categories']:
            matched_elements.append(f"Content type: {category}")
        
        # Specific term matches
        for term in query_analysis['content_terms']:
            if term in visual_description:
                matched_elements.append(f"Visual element: {term}")
            elif term in ocr_text:
                matched_elements.append(f"Text element: {term}")
        
        # NEW: Check filename for matches
        filename = screenshot.get('filename', '').lower()
        for word in query_lower.split():
            if len(word) > 2 and word in filename:
                matched_elements.append(f"Filename match: {word}")
        
        return matched_elements[:5] if matched_elements else ["General content match"]
    
    def search_by_text(self, query: str, limit: int = 5) -> List[SearchResult]:
        """Search by text content only."""
        screenshots = self.db_manager.get_all_processed_screenshots()
        
        matched_results = []
        query_lower = query.lower()
        
        for screenshot in screenshots:
            ocr_text = screenshot.get('ocr_text', '').lower()
            
            if query_lower in ocr_text:
                score = len(query_lower) / max(len(ocr_text), 1)
                
                result = SearchResult(
                    id=screenshot['id'],
                    filename=screenshot['filename'],
                    confidence_score=round(score * 100, 1),
                    preview_url=f"/uploads/{os.path.basename(screenshot['file_path'])}",
                    ocr_text=screenshot.get('ocr_text', ''),
                    visual_description=screenshot.get('visual_description', ''),
                    matched_elements=[f"Text match: '{query}'"]
                )
                
                matched_results.append((score, result))
        
        matched_results.sort(key=lambda x: x[0], reverse=True)
        return [result for _, result in matched_results[:limit]]