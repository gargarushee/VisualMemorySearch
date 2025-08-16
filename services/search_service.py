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
            
            # Calculate similarities and score each screenshot
            scored_results = []
            
            for screenshot in screenshots:
                # Skip screenshots without embeddings
                if not screenshot.get('text_embedding'):
                    continue
                
                # Calculate similarity score
                similarity_score = self.image_processor.calculate_similarity(
                    query_embedding, 
                    screenshot['text_embedding']
                )
                
                # Determine matched elements based on query and content
                matched_elements = self._find_matched_elements(
                    query, 
                    screenshot.get('ocr_text', ''), 
                    screenshot.get('visual_description', '')
                )
                
                # Create search result
                result = SearchResult(
                    id=screenshot['id'],
                    filename=screenshot['filename'],
                    confidence_score=round(similarity_score * 100, 1),  # Convert to percentage
                    preview_url=f"/uploads/{os.path.basename(screenshot['file_path'])}",
                    ocr_text=screenshot.get('ocr_text', ''),
                    visual_description=screenshot.get('visual_description', ''),
                    matched_elements=matched_elements
                )
                
                scored_results.append((similarity_score, result))
            
            # Sort by similarity score (descending)
            scored_results.sort(key=lambda x: x[0], reverse=True)
            
            # Return top results
            return [result for _, result in scored_results[:limit]]
        
        except Exception as e:
            print(f"Search error: {str(e)}")
            return []
    
    def _find_matched_elements(self, query: str, ocr_text: str, visual_description: str) -> List[str]:
        """Find elements that match the search query."""
        matched_elements = []
        
        query_lower = query.lower()
        ocr_lower = ocr_text.lower()
        visual_lower = visual_description.lower()
        
        # Check for direct text matches
        query_words = query_lower.split()
        
        for word in query_words:
            if len(word) > 3:  # Only check meaningful words
                if word in ocr_lower:
                    matched_elements.append(f"Text: '{word}' found in OCR")
                if word in visual_lower:
                    matched_elements.append(f"Visual: '{word}' found in description")
        
        # Check for common UI element patterns
        ui_patterns = {
            'button': ['button', 'btn', 'click'],
            'form': ['form', 'input', 'field'],
            'dialog': ['dialog', 'modal', 'popup'],
            'error': ['error', 'warning', 'alert'],
            'menu': ['menu', 'navigation', 'nav'],
            'login': ['login', 'sign in', 'authentication']
        }
        
        for pattern_name, keywords in ui_patterns.items():
            if any(keyword in query_lower for keyword in keywords):
                if any(keyword in visual_lower for keyword in keywords):
                    matched_elements.append(f"UI Element: {pattern_name} detected")
        
        # Remove duplicates and limit
        matched_elements = list(set(matched_elements))[:5]
        
        return matched_elements if matched_elements else ["General content match"]
    
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
