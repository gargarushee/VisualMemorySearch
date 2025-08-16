import os
from typing import List, Dict, Any
from models import SearchResult
from services.image_processor import ImageProcessor

class SearchService:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.image_processor = ImageProcessor()
    
    async def hybrid_search(self, query: str, limit: int = 5) -> List[SearchResult]:
        """Perform hybrid search combining text and visual similarity."""
        try:
            # Get all processed screenshots
            screenshots = self.db_manager.get_all_processed_screenshots()
            
            if not screenshots:
                return []
            
            # Create query embedding
            query_embedding = self.image_processor.create_embeddings(query)
            
            # Calculate similarities and score each screenshot with improved ranking
            scored_results = []
            
            for screenshot in screenshots:
                # Skip screenshots without embeddings
                if not screenshot.get('text_embedding'):
                    continue
                
                ocr_text = screenshot.get('ocr_text', '')
                visual_description = screenshot.get('visual_description', '')
                
                # Calculate base similarity score
                similarity_score = self.image_processor.calculate_similarity(
                    query_embedding, 
                    screenshot['text_embedding']
                )
                
                # Enhanced scoring with multiple factors
                final_score = similarity_score
                
                query_lower = query.lower()
                combined_text = f"{ocr_text} {visual_description}".lower()
                ocr_lower = ocr_text.lower()
                visual_lower = visual_description.lower()
                
                # Detect if this is a visual/image-focused query
                visual_keywords = ['picture', 'image', 'photo', 'show', 'mountain', 'river', 'landscape', 'nature', 'scenery', 'building', 'architecture', 'person', 'people', 'animal', 'car', 'food', 'sky', 'tree', 'flower', 'sunset', 'beach', 'forest', 'city', 'street']
                is_visual_query = any(keyword in query_lower for keyword in visual_keywords)
                
                # Boost for exact matches with priority based on query type
                if query_lower in combined_text:
                    if is_visual_query:
                        # For visual queries, prioritize visual description matches
                        if query_lower in visual_lower:
                            final_score += 0.8  # Very high boost for visual match
                        elif query_lower in ocr_lower:
                            final_score += 0.3  # Lower boost for text match on visual query
                        else:
                            final_score += 0.5  # Combined text match
                    else:
                        # For text queries, treat both equally
                        final_score += 0.6  # Major boost for exact query match
                
                # Boost for multi-word phrase matches with visual priority
                query_words = query_lower.split()
                if len(query_words) > 1:
                    for i in range(len(query_words) - 1):
                        phrase = ' '.join(query_words[i:i+2])
                        if is_visual_query:
                            # For visual queries, prioritize visual description phrase matches
                            if phrase in visual_lower:
                                final_score += 0.6  # High boost for visual phrase match
                            elif phrase in ocr_lower:
                                final_score += 0.2  # Lower boost for text phrase match
                        else:
                            # For text queries, treat phrase matches equally
                            if phrase in combined_text:
                                final_score += 0.4  # Good boost for phrase match
                
                # Special boost for authentication-related queries
                auth_terms = ['auth', 'authentication', 'login', 'sign in', 'password', 'credential']
                error_terms = ['error', 'warning', 'alert', 'problem', 'issue', 'fail']
                
                auth_in_query = any(term in query_lower for term in auth_terms)
                error_in_query = any(term in query_lower for term in error_terms)
                
                if auth_in_query and error_in_query:
                    # Super high boost for error + auth combinations
                    auth_count = sum(1 for term in auth_terms if term in combined_text)
                    error_count = sum(1 for term in error_terms if term in combined_text)
                    if auth_count > 0 and error_count > 0:
                        final_score += 0.8  # Very high boost for error+auth combo
                    elif auth_count > 0 or error_count > 0:
                        final_score += 0.5  # Good boost for partial match
                
                # Special boost for UI element + color combinations
                if 'blue' in query_lower and 'button' in query_lower:
                    if ('blue' in combined_text and 'button' in combined_text):
                        final_score += 0.4  # High boost for color+element combo
                
                # Enhanced keyword matching with visual priority
                important_words = [w for w in query_words if len(w) > 2]
                
                if important_words and is_visual_query:
                    # For visual queries, heavily weight visual description matches
                    visual_matches = sum(1 for word in important_words if word in visual_lower)
                    ocr_matches = sum(1 for word in important_words if word in ocr_lower)
                    
                    if visual_matches > 0:
                        visual_match_ratio = visual_matches / len(important_words)
                        final_score += visual_match_ratio * 0.4  # High boost for visual matches
                    
                    if ocr_matches > 0:
                        ocr_match_ratio = ocr_matches / len(important_words)
                        final_score += ocr_match_ratio * 0.1  # Small boost for text matches
                        
                    # Penalty for likely irrelevant matches
                    text_heavy_indicators = ['error', 'warning', 'login', 'password', 'form', 'button', 'dialog', 'menu']
                    if any(indicator in combined_text for indicator in text_heavy_indicators) and visual_matches == 0:
                        final_score -= 0.3  # Penalty for UI/text content when searching for images
                
                elif important_words:
                    # For non-visual queries, treat both sources equally
                    word_matches = sum(1 for word in important_words if word in combined_text)
                    word_match_ratio = word_matches / len(important_words)
                    final_score += word_match_ratio * 0.2
                
                # Determine matched elements
                matched_elements = self._find_matched_elements(
                    query, ocr_text, visual_description
                )
                
                # Additional boost based on number of quality matches
                quality_matches = [m for m in matched_elements if 'Exact match' in m or 'Phrase' in m]
                final_score += len(quality_matches) * 0.1
                
                # Create search result
                result = SearchResult(
                    id=screenshot['id'],
                    filename=screenshot['filename'],
                    confidence_score=round(min(final_score * 100, 100), 1),  # Cap at 100%
                    preview_url=f"/uploads/{os.path.basename(screenshot['file_path'])}",
                    ocr_text=ocr_text,
                    visual_description=visual_description,
                    matched_elements=matched_elements
                )
                
                scored_results.append((final_score, result))
            
            # Sort by similarity score (descending)
            scored_results.sort(key=lambda x: x[0], reverse=True)
            
            # Return top results
            return [result for _, result in scored_results[:limit]]
        
        except Exception as e:
            print(f"Search error: {str(e)}")
            return []
    
    def _find_matched_elements(self, query: str, ocr_text: str, visual_description: str) -> List[str]:
        """Find elements that match the search query with improved scoring."""
        matched_elements = []
        
        query_lower = query.lower()
        ocr_lower = ocr_text.lower()
        visual_lower = visual_description.lower()
        
        # Enhanced UI element patterns with more comprehensive keywords
        ui_patterns = {
            'button': ['button', 'btn', 'click', 'press', 'tap'],
            'blue_button': ['blue button', 'blue btn', 'button blue'],
            'form': ['form', 'input', 'field', 'textbox', 'text box'],
            'dialog': ['dialog', 'modal', 'popup', 'window', 'alert box'],
            'error': ['error', 'warning', 'alert', 'problem', 'issue'],
            'menu': ['menu', 'navigation', 'nav', 'dropdown', 'list'],
            'login': ['login', 'sign in', 'authentication', 'auth', 'password'],
            'color_blue': ['blue', 'azure', 'navy', 'cyan'],
            'color_red': ['red', 'crimson', 'scarlet'],
            'color_green': ['green', 'emerald', 'lime'],
            'cancel': ['cancel', 'close', 'dismiss', 'exit'],
            'save': ['save', 'submit', 'confirm', 'apply']
        }
        
        # Visual content patterns with high priority for image queries
        visual_patterns = {
            'mountain': ['mountain', 'mountains', 'peak', 'peaks', 'summit', 'hill', 'hills', 'range'],
            'nature': ['nature', 'landscape', 'scenery', 'outdoor', 'wilderness'],
            'water': ['river', 'lake', 'ocean', 'sea', 'water', 'stream', 'beach', 'waterfall'],
            'sky': ['sky', 'cloud', 'clouds', 'sunset', 'sunrise', 'horizon'],
            'forest': ['forest', 'tree', 'trees', 'woods', 'jungle'],
            'city': ['city', 'building', 'buildings', 'urban', 'street', 'road'],
            'people': ['person', 'people', 'man', 'woman', 'child', 'group'],
            'animal': ['animal', 'animals', 'bird', 'dog', 'cat', 'wildlife'],
            'food': ['food', 'meal', 'dish', 'restaurant', 'kitchen', 'cooking']
        }
        
        # Check for exact phrase matches (highest priority)
        if query_lower in ocr_lower:
            matched_elements.append(f"Exact match: '{query}' in text")
        if query_lower in visual_lower:
            matched_elements.append(f"Exact match: '{query}' in visual")
        
        # Check for multi-word phrases
        query_words = query_lower.split()
        if len(query_words) > 1:
            for i in range(len(query_words) - 1):
                phrase = ' '.join(query_words[i:i+2])
                if phrase in ocr_lower:
                    matched_elements.append(f"Phrase: '{phrase}' in text")
                if phrase in visual_lower:
                    matched_elements.append(f"Phrase: '{phrase}' in visual")
        
        # Check individual words
        for word in query_words:
            if len(word) > 2:
                if word in ocr_lower:
                    matched_elements.append(f"Word: '{word}' in text")
                if word in visual_lower:
                    matched_elements.append(f"Word: '{word}' in visual")
        
        # Check visual and UI patterns with priority scoring
        pattern_matches = []
        
        # Detect if this is likely a visual query
        visual_query_indicators = ['picture', 'photo', 'image', 'show', 'landscape', 'scenery']
        is_visual_query = any(indicator in query_lower for indicator in visual_query_indicators)
        
        if is_visual_query:
            # Prioritize visual patterns for image queries
            for pattern_name, keywords in visual_patterns.items():
                for keyword in keywords:
                    if keyword in query_lower:
                        if keyword in visual_lower:
                            priority = 3.0  # Very high priority for visual content matches
                            pattern_matches.append((priority, f"Visual: {pattern_name}"))
                        elif keyword in ocr_lower:
                            priority = 1.5  # Lower priority for text matches in visual queries
                            pattern_matches.append((priority, f"Text: {pattern_name}"))
                        break
        else:
            # For non-visual queries, check visual patterns with normal priority
            for pattern_name, keywords in visual_patterns.items():
                for keyword in keywords:
                    if keyword in query_lower:
                        if keyword in visual_lower or keyword in ocr_lower:
                            priority = 2.0
                            pattern_matches.append((priority, f"Content: {pattern_name}"))
                        break
        
        # Check UI patterns
        for pattern_name, keywords in ui_patterns.items():
            for keyword in keywords:
                if keyword in query_lower:
                    if keyword in visual_lower or keyword in ocr_lower:
                        priority = 2.0 if not is_visual_query else 1.0  # Lower priority for UI in visual queries
                        if 'blue' in pattern_name and 'blue' in query_lower:
                            priority += 0.5  # Boost for color+element combos
                        pattern_matches.append((priority, f"UI: {pattern_name.replace('_', ' ')}"))
                    break
        
        # Sort pattern matches by priority and add to results
        pattern_matches.sort(key=lambda x: x[0], reverse=True)
        matched_elements.extend([match[1] for match in pattern_matches[:3]])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_matches = []
        for match in matched_elements:
            if match not in seen:
                seen.add(match)
                unique_matches.append(match)
        
        return unique_matches[:5] if unique_matches else ["General content match"]
    
    def search_by_text(self, query: str, limit: int = 5) -> List[SearchResult]:
        """Search by text content only."""
        # This is a simplified version focusing on OCR text
        screenshots = self.db_manager.get_all_processed_screenshots()
        
        matched_results = []
        query_lower = query.lower()
        
        for screenshot in screenshots:
            ocr_text = screenshot.get('ocr_text', '').lower()
            
            if query_lower in ocr_text:
                # Simple text matching score
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
        
        # Sort by score
        matched_results.sort(key=lambda x: x[0], reverse=True)
        
        return [result for _, result in matched_results[:limit]]
