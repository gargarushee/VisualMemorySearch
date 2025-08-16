#!/usr/bin/env python3
"""
Test cases for Visual Memory Search algorithm using uploaded images.
This file tests the search algorithm against real uploaded images to ensure proper ranking.
"""

import asyncio
import sys
import os
sys.path.append('.')

from database import DatabaseManager
from services.search_service import SearchService

class SearchTestSuite:
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.search_service = SearchService(self.db_manager)
        
    async def run_all_tests(self):
        """Run all test cases and report results."""
        print("🔍 Visual Memory Search - Test Suite")
        print("=" * 50)
        
        test_cases = [
            {
                'name': 'Mountain Pictures Query',
                'query': 'show mountain pictures',
                'expected_behavior': 'Should prioritize actual mountain/landscape images over UI screenshots',
                'should_exclude': ['Screenshot 2025-08-16 at 11.05.30 AM.png', 'Screenshot 2025-08-16 at 11.05.36 AM.png'],
                'should_include_types': ['mountain', 'landscape', 'nature'],
                'test_function': self.test_mountain_pictures
            },
            {
                'name': 'Error Message About Auth',
                'query': 'error message about auth',
                'expected_behavior': 'Should prioritize auth error screenshots over nature images',
                'should_include': ['Screenshot 2025-08-16 at 11.05.30 AM.png'],
                'should_exclude_types': ['nature', 'landscape'],
                'test_function': self.test_auth_error
            },
            {
                'name': 'River Images Query',
                'query': 'river images',
                'expected_behavior': 'Should show river images, not mountain-only images',
                'should_include_types': ['river', 'water'],
                'should_exclude': ['Screenshot 2025-08-16 at 11.05.30 AM.png', 'Screenshot 2025-08-16 at 11.05.36 AM.png'],
                'test_function': self.test_river_images
            },
            {
                'name': 'Blue Button Query',
                'query': 'screenshot with blue button',
                'expected_behavior': 'Should prioritize UI screenshots with blue buttons',
                'should_include_types': ['button', 'blue', 'ui'],
                'should_exclude_types': ['nature', 'landscape'],
                'test_function': self.test_blue_button
            },
            {
                'name': 'Nature Landscape Query',
                'query': 'nature landscape',
                'expected_behavior': 'Should prioritize outdoor/nature images over UI screenshots',
                'should_exclude_types': ['ui', 'interface', 'form'],
                'should_include_types': ['nature', 'landscape', 'outdoor'],
                'test_function': self.test_nature_landscape
            }
        ]
        
        passed = 0
        total = len(test_cases)
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n📋 Test {i}/{total}: {test_case['name']}")
            print(f"Query: '{test_case['query']}'")
            print(f"Expected: {test_case['expected_behavior']}")
            
            try:
                result = await test_case['test_function'](test_case)
                if result['passed']:
                    print("✅ PASSED")
                    passed += 1
                else:
                    print("❌ FAILED")
                    for issue in result['issues']:
                        print(f"   - {issue}")
            except Exception as e:
                print(f"❌ ERROR: {str(e)}")
        
        print(f"\n🎯 Test Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed! Search algorithm is working correctly.")
        else:
            print("⚠️  Some tests failed. Search algorithm needs improvement.")
        
        return passed, total
    
    async def test_mountain_pictures(self, test_case):
        """Test mountain pictures query."""
        results = await self.search_service.hybrid_search(test_case['query'], limit=5)
        
        issues = []
        
        # Check that auth screenshots are not in top results
        if 'should_exclude' in test_case:
            for exclude_file in test_case['should_exclude']:
                for i, result in enumerate(results[:3]):  # Check top 3 results
                    if exclude_file in result.filename:
                        issues.append(f"Excluded file '{exclude_file}' appears in position {i+1}")
        
        # Check that nature content is prioritized
        nature_found = False
        for result in results[:2]:  # Check top 2 results
            desc_lower = result.visual_description.lower()
            if any(term in desc_lower for term in ['mountain', 'landscape', 'nature', 'outdoor', 'scenery']):
                nature_found = True
                break
        
        if not nature_found and len(results) > 0:
            issues.append("No nature/landscape content found in top 2 results")
        
        return {
            'passed': len(issues) == 0,
            'issues': issues,
            'results': [(r.filename, r.confidence_score) for r in results[:3]]
        }
    
    async def test_auth_error(self, test_case):
        """Test authentication error query."""
        results = await self.search_service.hybrid_search(test_case['query'], limit=5)
        
        issues = []
        
        # Check that auth-related screenshots are prioritized
        auth_found = False
        for result in results[:2]:
            desc_lower = f"{result.ocr_text} {result.visual_description}".lower()
            if any(term in desc_lower for term in ['auth', 'login', 'error', 'password', 'sign in']):
                auth_found = True
                break
        
        if not auth_found and len(results) > 0:
            issues.append("No authentication/error content found in top 2 results")
        
        # Check that nature images are not prioritized
        for i, result in enumerate(results[:2]):
            desc_lower = result.visual_description.lower()
            if any(term in desc_lower for term in ['mountain', 'river', 'landscape', 'nature']):
                issues.append(f"Nature content inappropriately ranked at position {i+1} for auth query")
        
        return {
            'passed': len(issues) == 0,
            'issues': issues,
            'results': [(r.filename, r.confidence_score) for r in results[:3]]
        }
    
    async def test_river_images(self, test_case):
        """Test river images query."""
        results = await self.search_service.hybrid_search(test_case['query'], limit=5)
        
        issues = []
        
        # Check that water/river content is prioritized
        water_found = False
        for result in results[:2]:
            desc_lower = result.visual_description.lower()
            if any(term in desc_lower for term in ['river', 'water', 'stream', 'lake']):
                water_found = True
                break
        
        if not water_found and len(results) > 0:
            issues.append("No water/river content found in top 2 results")
        
        # Check that UI screenshots are excluded
        for i, result in enumerate(results[:3]):
            if 'Screenshot 2025-08-16' in result.filename:
                issues.append(f"UI screenshot inappropriately ranked at position {i+1} for river query")
        
        return {
            'passed': len(issues) == 0,
            'issues': issues,
            'results': [(r.filename, r.confidence_score) for r in results[:3]]
        }
    
    async def test_blue_button(self, test_case):
        """Test blue button query."""
        results = await self.search_service.hybrid_search(test_case['query'], limit=5)
        
        issues = []
        
        # Check that UI content with buttons is prioritized
        ui_found = False
        for result in results[:2]:
            desc_lower = f"{result.ocr_text} {result.visual_description}".lower()
            if any(term in desc_lower for term in ['button', 'blue', 'interface', 'ui']):
                ui_found = True
                break
        
        if not ui_found and len(results) > 0:
            issues.append("No UI/button content found in top 2 results")
        
        # Check that nature images are not prioritized
        for i, result in enumerate(results[:2]):
            desc_lower = result.visual_description.lower()
            if any(term in desc_lower for term in ['mountain', 'river', 'landscape', 'nature']) and not any(term in desc_lower for term in ['button', 'blue']):
                issues.append(f"Pure nature content inappropriately ranked at position {i+1} for button query")
        
        return {
            'passed': len(issues) == 0,
            'issues': issues,
            'results': [(r.filename, r.confidence_score) for r in results[:3]]
        }
    
    async def test_nature_landscape(self, test_case):
        """Test nature landscape query."""
        results = await self.search_service.hybrid_search(test_case['query'], limit=5)
        
        issues = []
        
        # Check that nature content is prioritized
        nature_found = False
        for result in results[:2]:
            desc_lower = result.visual_description.lower()
            if any(term in desc_lower for term in ['nature', 'landscape', 'outdoor', 'scenery', 'mountain', 'forest']):
                nature_found = True
                break
        
        if not nature_found and len(results) > 0:
            issues.append("No nature/landscape content found in top 2 results")
        
        return {
            'passed': len(issues) == 0,
            'issues': issues,
            'results': [(r.filename, r.confidence_score) for r in results[:3]]
        }
    
    async def debug_search_results(self, query: str):
        """Debug helper to see detailed search results."""
        print(f"\n🔍 Debug Search: '{query}'")
        print("-" * 40)
        
        results = await self.search_service.hybrid_search(query, limit=5)
        
        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result.filename} (Score: {result.confidence_score}%)")
            print(f"   OCR Text: {result.ocr_text[:100]}...")
            print(f"   Visual Desc: {result.visual_description[:100]}...")
            print(f"   Matched: {', '.join(result.matched_elements)}")

async def main():
    """Run the test suite."""
    test_suite = SearchTestSuite()
    
    # Check if we should run debug mode
    if len(sys.argv) > 1 and sys.argv[1] == 'debug':
        query = input("Enter query to debug: ")
        await test_suite.debug_search_results(query)
    else:
        passed, total = await test_suite.run_all_tests()
        
        # Exit with appropriate code
        sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    asyncio.run(main())