#!/usr/bin/env python3
"""
Comprehensive test suite for complex song disambiguation scenarios.

Tests the enhanced SongDisambiguator with:
1. Full song names extracted from natural language
2. Vague references that need context understanding
3. Descriptive queries (actions, characteristics, lyrics)
4. Partial descriptions with artist hints
5. Ambiguous queries with multiple alternatives
"""

import sys
import os
import json
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils import load_config
from src.llm import SongDisambiguator


def test_full_song_name():
    """Test 1: Full Song Name Extraction"""
    print("=" * 80)
    print("TEST 1: Full Song Name Extraction")
    print("=" * 80)
    
    config = load_config()
    disambiguator = SongDisambiguator(config)
    
    test_cases = [
        {
            "input": "play a song called breaking the habit on Spotify",
            "expected_song": "Breaking the Habit",
            "expected_artist": "Linkin Park",
            "min_confidence": 0.9
        },
        {
            "input": "song called space song",
            "expected_song": "Space Song",
            "expected_artist": "Beach House",
            "min_confidence": 0.85
        }
    ]
    
    passed = 0
    failed = 0
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test_case['input']}")
        try:
            result = disambiguator.disambiguate(test_case['input'])
            
            song_name = result.get('song_name', '').lower()
            artist = result.get('artist', '').lower() if result.get('artist') else ''
            confidence = result.get('confidence', 0)
            
            print(f"  Result: '{result.get('song_name')}' by {result.get('artist', 'Unknown')}")
            print(f"  Confidence: {confidence:.2f}")
            print(f"  Reasoning: {result.get('reasoning', 'N/A')[:100]}...")
            
            # Success criteria
            song_match = test_case['expected_song'].lower() in song_name or song_name in test_case['expected_song'].lower()
            artist_match = test_case['expected_artist'].lower() in artist or artist in test_case['expected_artist'].lower()
            confidence_ok = confidence >= test_case['min_confidence']
            
            if song_match and artist_match and confidence_ok:
                print(f"  ✅ PASSED")
                passed += 1
            else:
                print(f"  ❌ FAILED")
                if not song_match:
                    print(f"    - Song name mismatch: expected '{test_case['expected_song']}', got '{result.get('song_name')}'")
                if not artist_match:
                    print(f"    - Artist mismatch: expected '{test_case['expected_artist']}', got '{result.get('artist')}'")
                if not confidence_ok:
                    print(f"    - Confidence too low: {confidence:.2f} < {test_case['min_confidence']}")
                failed += 1
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            failed += 1
    
    print(f"\nSummary: {passed} passed, {failed} failed")
    return failed == 0


def test_vague_reference():
    """Test 2: Vague References"""
    print("\n" + "=" * 80)
    print("TEST 2: Vague References")
    print("=" * 80)
    
    config = load_config()
    disambiguator = SongDisambiguator(config)
    
    test_cases = [
        {
            "input": "the space song",
            "expected_song": "Space Song",
            "expected_artist": "Beach House",
            "min_confidence": 0.8
        }
    ]
    
    passed = 0
    failed = 0
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test_case['input']}")
        try:
            result = disambiguator.disambiguate(test_case['input'])
            
            song_name = result.get('song_name', '').lower()
            artist = result.get('artist', '').lower() if result.get('artist') else ''
            confidence = result.get('confidence', 0)
            
            print(f"  Result: '{result.get('song_name')}' by {result.get('artist', 'Unknown')}")
            print(f"  Confidence: {confidence:.2f}")
            print(f"  Reasoning: {result.get('reasoning', 'N/A')[:100]}...")
            
            # Success criteria
            song_match = test_case['expected_song'].lower() in song_name or song_name in test_case['expected_song'].lower()
            artist_match = test_case['expected_artist'].lower() in artist or artist in test_case['expected_artist'].lower()
            confidence_ok = confidence >= test_case['min_confidence']
            
            if song_match and artist_match and confidence_ok:
                print(f"  ✅ PASSED")
                passed += 1
            else:
                print(f"  ❌ FAILED")
                if not song_match:
                    print(f"    - Song name mismatch")
                if not artist_match:
                    print(f"    - Artist mismatch")
                if not confidence_ok:
                    print(f"    - Confidence too low")
                failed += 1
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            failed += 1
    
    print(f"\nSummary: {passed} passed, {failed} failed")
    return failed == 0


def test_descriptive_query():
    """Test 3: Descriptive Queries"""
    print("\n" + "=" * 80)
    print("TEST 3: Descriptive Queries")
    print("=" * 80)
    
    config = load_config()
    disambiguator = SongDisambiguator(config)
    
    test_cases = [
        {
            "input": "play that song by Michael Jackson where he move like he moonwalks",
            "expected_song": "Smooth Criminal",
            "expected_artist": "Michael Jackson",
            "min_confidence": 0.85
        }
    ]
    
    passed = 0
    failed = 0
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test_case['input']}")
        try:
            result = disambiguator.disambiguate(test_case['input'])
            
            song_name = result.get('song_name', '').lower()
            artist = result.get('artist', '').lower() if result.get('artist') else ''
            confidence = result.get('confidence', 0)
            
            print(f"  Result: '{result.get('song_name')}' by {result.get('artist', 'Unknown')}")
            print(f"  Confidence: {confidence:.2f}")
            print(f"  Reasoning: {result.get('reasoning', 'N/A')[:150]}...")
            
            # Success criteria
            song_match = test_case['expected_song'].lower() in song_name or song_name in test_case['expected_song'].lower()
            artist_match = test_case['expected_artist'].lower() in artist or artist in test_case['expected_artist'].lower()
            confidence_ok = confidence >= test_case['min_confidence']
            
            if song_match and artist_match and confidence_ok:
                print(f"  ✅ PASSED")
                passed += 1
            else:
                print(f"  ❌ FAILED")
                if not song_match:
                    print(f"    - Song name mismatch: expected '{test_case['expected_song']}', got '{result.get('song_name')}'")
                if not artist_match:
                    print(f"    - Artist mismatch: expected '{test_case['expected_artist']}', got '{result.get('artist')}'")
                if not confidence_ok:
                    print(f"    - Confidence too low: {confidence:.2f} < {test_case['min_confidence']}")
                failed += 1
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            failed += 1
    
    print(f"\nSummary: {passed} passed, {failed} failed")
    return failed == 0


def test_partial_description():
    """Test 4: Partial Descriptions with Artist Hints"""
    print("\n" + "=" * 80)
    print("TEST 4: Partial Descriptions with Artist Hints")
    print("=" * 80)
    
    config = load_config()
    disambiguator = SongDisambiguator(config)
    
    test_cases = [
        {
            "input": "play that song that's something around it's it starts with space by Eminem",
            "expected_song": "Space Bound",
            "expected_artist": "Eminem",
            "min_confidence": 0.8
        },
        {
            "input": "song that starts with space by Eminem",
            "expected_song": "Space Bound",
            "expected_artist": "Eminem",
            "min_confidence": 0.8
        }
    ]
    
    passed = 0
    failed = 0
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test_case['input']}")
        try:
            result = disambiguator.disambiguate(test_case['input'])
            
            song_name = result.get('song_name', '').lower()
            artist = result.get('artist', '').lower() if result.get('artist') else ''
            confidence = result.get('confidence', 0)
            
            print(f"  Result: '{result.get('song_name')}' by {result.get('artist', 'Unknown')}")
            print(f"  Confidence: {confidence:.2f}")
            print(f"  Reasoning: {result.get('reasoning', 'N/A')[:150]}...")
            
            # Success criteria
            song_match = test_case['expected_song'].lower() in song_name or song_name in test_case['expected_song'].lower()
            artist_match = test_case['expected_artist'].lower() in artist or artist in test_case['expected_artist'].lower()
            confidence_ok = confidence >= test_case['min_confidence']
            
            if song_match and artist_match and confidence_ok:
                print(f"  ✅ PASSED")
                passed += 1
            else:
                print(f"  ❌ FAILED")
                if not song_match:
                    print(f"    - Song name mismatch: expected '{test_case['expected_song']}', got '{result.get('song_name')}'")
                if not artist_match:
                    print(f"    - Artist mismatch: expected '{test_case['expected_artist']}', got '{result.get('artist')}'")
                if not confidence_ok:
                    print(f"    - Confidence too low: {confidence:.2f} < {test_case['min_confidence']}")
                failed += 1
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            failed += 1
    
    print(f"\nSummary: {passed} passed, {failed} failed")
    return failed == 0


def test_ambiguous_query():
    """Test 5: Ambiguous Queries with Alternatives"""
    print("\n" + "=" * 80)
    print("TEST 5: Ambiguous Queries with Alternatives")
    print("=" * 80)
    
    config = load_config()
    disambiguator = SongDisambiguator(config)
    
    test_cases = [
        {
            "input": "that hello song",
            "expected_alternatives": ["Adele", "Lionel Richie", "Evanescence"],
            "min_confidence": 0.7
        }
    ]
    
    passed = 0
    failed = 0
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test_case['input']}")
        try:
            result = disambiguator.disambiguate(test_case['input'])
            
            song_name = result.get('song_name', '')
            artist = result.get('artist', '')
            confidence = result.get('confidence', 0)
            alternatives = result.get('alternatives', [])
            
            print(f"  Result: '{song_name}' by {artist}")
            print(f"  Confidence: {confidence:.2f}")
            print(f"  Alternatives: {len(alternatives)}")
            for alt in alternatives:
                print(f"    - {alt.get('song_name')} by {alt.get('artist', 'Unknown')}")
            
            # Success criteria
            confidence_ok = confidence >= test_case['min_confidence']
            has_alternatives = len(alternatives) > 0
            
            # Check if at least one expected alternative is present
            alt_artists = [alt.get('artist', '').lower() for alt in alternatives]
            expected_found = any(
                exp.lower() in alt_artist or alt_artist in exp.lower()
                for exp in test_case['expected_alternatives']
                for alt_artist in alt_artists
            )
            
            if confidence_ok and has_alternatives and expected_found:
                print(f"  ✅ PASSED")
                passed += 1
            else:
                print(f"  ❌ FAILED")
                if not confidence_ok:
                    print(f"    - Confidence too low: {confidence:.2f} < {test_case['min_confidence']}")
                if not has_alternatives:
                    print(f"    - No alternatives provided")
                if not expected_found:
                    print(f"    - Expected alternatives not found")
                failed += 1
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            failed += 1
    
    print(f"\nSummary: {passed} passed, {failed} failed")
    return failed == 0


def run_all_tests():
    """Run all complex disambiguation tests."""
    print("\n" + "=" * 80)
    print("COMPLEX SONG DISAMBIGUATION TEST SUITE")
    print("=" * 80)
    
    tests = [
        ("Full Song Name", test_full_song_name),
        ("Vague Reference", test_vague_reference),
        ("Descriptive Query", test_descriptive_query),
        ("Partial Description", test_partial_description),
        ("Ambiguous Query", test_ambiguous_query),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result, None))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' crashed: {e}")
            results.append((test_name, False, str(e)))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    for test_name, success, error in results:
        status = "✅ PASSED" if success else f"❌ FAILED: {error or 'Test failed'}"
        print(f"  {test_name}: {status}")
    
    print(f"\nTotal: {passed}/{total} test suites passed")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

