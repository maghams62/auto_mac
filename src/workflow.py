"""
Workflow orchestrator that ties together all components.
"""

import logging
from typing import Dict, Any, Optional

from .llm import LLMPlanner
from .documents import DocumentIndexer, DocumentParser, SemanticSearch, DocumentScreenshot
from .automation import MailComposer, KeynoteComposer, PagesComposer


logger = logging.getLogger(__name__)


class WorkflowOrchestrator:
    """
    Orchestrates the complete workflow from user intent to email composition.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the workflow orchestrator.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self._indexer = None  # Lazy-loaded DocumentIndexer
        self._search = None  # Lazy-loaded SemanticSearch

        # Initialize lightweight components immediately
        logger.info("Initializing workflow components...")

        self.planner = LLMPlanner(config)
        self.parser = DocumentParser(config)
        self.mail_composer = MailComposer(config)
        self.screenshotter = DocumentScreenshot(config)
        self.keynote_composer = KeynoteComposer(config)
        self.pages_composer = PagesComposer(config)

        logger.info("Workflow components initialized (DocumentIndexer will be lazy-loaded)")
    
    @property
    def indexer(self):
        """Lazy-load DocumentIndexer on first access to improve startup time."""
        if self._indexer is None:
            logger.info("[PERF] Initializing DocumentIndexer (lazy load)")
            self._indexer = DocumentIndexer(self.config)
            logger.info("[PERF] DocumentIndexer initialized")
        return self._indexer
    
    @property
    def search(self):
        """Lazy-load SemanticSearch on first access (depends on indexer)."""
        if self._search is None:
            logger.info("[PERF] Initializing SemanticSearch (lazy load)")
            self._search = SemanticSearch(self.indexer, self.config)
            logger.info("[PERF] SemanticSearch initialized")
        return self._search

    def execute(self, user_input: str) -> Dict[str, Any]:
        """
        Execute the complete workflow for a user request.

        Args:
            user_input: Natural language request from user

        Returns:
            Dictionary with execution results and status
        """
        logger.info(f"Executing workflow for: {user_input}")

        result = {
            'success': False,
            'user_input': user_input,
            'steps': [],
            'error': None,
        }

        try:
            # Step 1: Parse intent
            logger.info("Step 1: Parsing intent")
            intent_data = self.planner.parse_intent(user_input)
            result['steps'].append({
                'step': 'parse_intent',
                'status': 'success',
                'data': intent_data,
            })

            intent = intent_data.get('intent')
            params = intent_data.get('parameters', {})

            # Route to appropriate workflow based on intent
            if intent == 'create_presentation':
                return self._execute_presentation_workflow(params, result)
            elif intent == 'create_document':
                return self._execute_document_workflow(params, result)
            elif intent != 'find_and_email_document':
                result['error'] = f"Unsupported intent: {intent}"
                return result

            # Step 2: Search documents
            logger.info("Step 2: Searching documents")
            search_query = params.get('search_query', '')

            # Use original query for semantic search (refinement adds OR operators which confuse embeddings)
            search_results = self.search.search_and_group(search_query)

            if not search_results:
                result['error'] = "No documents found matching the query"
                result['steps'].append({
                    'step': 'search_documents',
                    'status': 'failed',
                    'data': {'query': search_query, 'results': []},
                })
                return result

            result['steps'].append({
                'step': 'search_documents',
                'status': 'success',
                'data': {
                    'query': search_query,
                    'results_count': len(search_results),
                    'top_match': search_results[0]['file_name'],
                },
            })

            # Step 3: Select best document
            logger.info("Step 3: Selecting best document")
            best_doc = search_results[0]
            file_path = best_doc['file_path']

            result['steps'].append({
                'step': 'select_document',
                'status': 'success',
                'data': {
                    'file_path': file_path,
                    'file_name': best_doc['file_name'],
                    'similarity': best_doc['max_similarity'],
                },
            })

            # Step 4: Plan extraction
            logger.info("Step 4: Planning section extraction")
            section_request = params.get('document_section', 'all')

            document_metadata = {
                'file_name': best_doc['file_name'],
                'file_type': best_doc['file_type'],
                'total_pages': best_doc['total_pages'],
            }

            extraction_plan = self.planner.plan_section_extraction(
                document_metadata, section_request
            )

            result['steps'].append({
                'step': 'plan_extraction',
                'status': 'success',
                'data': extraction_plan,
            })

            # Step 5: Extract content
            logger.info("Step 5: Extracting content")
            extracted_content = self.parser.extract_section(
                file_path, extraction_plan
            )

            if not extracted_content:
                result['error'] = "Failed to extract content from document"
                result['steps'].append({
                    'step': 'extract_content',
                    'status': 'failed',
                })
                return result

            result['steps'].append({
                'step': 'extract_content',
                'status': 'success',
                'data': {
                    'content_length': len(extracted_content),
                    'preview': extracted_content[:200] + '...',
                },
            })

            # Step 5.5: Handle screenshot request if enabled
            screenshot_files = []
            screenshot_request = params.get('screenshot_request', {})

            if screenshot_request.get('enabled'):
                logger.info("Step 5.5: Taking screenshots")

                page_numbers = screenshot_request.get('page_numbers')
                search_text = screenshot_request.get('search_text')

                screenshot_files = self.screenshotter.screenshot_pages(
                    file_path=file_path,
                    page_numbers=page_numbers,
                    search_text=search_text,
                )

                if screenshot_files:
                    result['steps'].append({
                        'step': 'take_screenshots',
                        'status': 'success',
                        'data': {
                            'screenshot_count': len(screenshot_files),
                            'files': screenshot_files,
                        },
                    })
                    # Update content to mention screenshots instead of text
                    extracted_content = f"Screenshots attached ({len(screenshot_files)} image(s))"
                else:
                    result['steps'].append({
                        'step': 'take_screenshots',
                        'status': 'failed',
                        'data': {'error': 'No screenshots generated'},
                    })

            # Step 6: Compose email
            logger.info("Step 6: Composing email")
            email_action = params.get('email_action', {})

            email_data = self.planner.compose_email(
                subject=email_action.get('subject', best_doc['file_name']),
                content=extracted_content,
                instructions=email_action.get('body_instructions', 'Include the content'),
            )

            result['steps'].append({
                'step': 'compose_email',
                'status': 'success',
                'data': email_data,
            })

            # Step 7: Open in Mail.app
            logger.info("Step 7: Opening in Mail.app")
            recipient = email_action.get('recipient')

            # Prepare attachments
            all_attachments = []
            if screenshot_files:
                # If screenshots were taken, attach them instead of the original file
                all_attachments.extend(screenshot_files)
            else:
                # Otherwise attach the original document
                all_attachments.append(file_path)

            mail_success = self.mail_composer.compose_email(
                subject=email_data['subject'],
                body=email_data['body'],
                recipient=recipient,
                attachment_paths=all_attachments,
                send_immediately=True,  # Auto-send the email
            )

            if not mail_success:
                result['error'] = "Failed to compose email in Mail.app"
                result['steps'].append({
                    'step': 'open_mail',
                    'status': 'failed',
                })
                return result

            result['steps'].append({
                'step': 'open_mail',
                'status': 'success',
                'data': {'recipient': recipient},
            })

            # Success!
            result['success'] = True
            result['summary'] = email_data.get('summary', 'Email composed successfully')

            logger.info("Workflow completed successfully")

        except Exception as e:
            logger.error(f"Workflow error: {e}", exc_info=True)
            result['error'] = str(e)

        return result

    def reindex_documents(self, cancel_event=None) -> Dict[str, Any]:
        """
        Reindex all documents from configured folders in config.yaml.

        This method ONLY indexes folders specified in config.yaml under documents.folders.
        It does not accept custom folder paths - use index_documents() directly for that.

        Args:
            cancel_event: Optional asyncio.Event to signal cancellation

        Returns:
            Indexing statistics
        """
        logger.info("Starting document reindexing from config.yaml folders")
        
        # Get folders from config to log them
        config_folders = self.config.get('documents', {}).get('folders', [])
        logger.info(f"Will index documents from configured folders: {config_folders}")

        try:
            # Pass None to ensure it uses config folders only
            count = self.indexer.index_documents(folders=None, cancel_event=cancel_event)
            
            # Check if cancelled
            if cancel_event and cancel_event.is_set():
                logger.info("Indexing cancelled by user")
                return {
                    'success': False,
                    'cancelled': True,
                    'error': 'Indexing cancelled by user',
                }
            
            stats = self.indexer.get_stats()

            return {
                'success': True,
                'indexed_documents': count,
                'stats': stats,
            }

        except Exception as e:
            logger.error(f"Reindexing error: {e}")
            return {
                'success': False,
                'error': str(e),
            }

    def test_components(self) -> Dict[str, bool]:
        """
        Test all components.

        Returns:
            Dictionary with component test results
        """
        logger.info("Testing components")

        results = {}

        # Test Mail.app
        results['mail_app'] = self.mail_composer.test_mail_integration()

        # Test FAISS index
        results['index_loaded'] = (
            self.indexer.index is not None and
            len(self.indexer.documents) > 0
        )

        # Test OpenAI API (basic check)
        try:
            test_embedding = self.indexer.get_embedding("test")
            results['openai_api'] = test_embedding is not None
        except:
            results['openai_api'] = False

        return results

    def _execute_presentation_workflow(
        self, params: Dict[str, Any], result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute workflow for creating a Keynote presentation.

        Args:
            params: Parameters from intent parsing
            result: Result dictionary to update

        Returns:
            Updated result dictionary
        """
        try:
            # Step 2: Search for document
            logger.info("Step 2: Searching for source document")
            search_query = params.get('search_query', '')
            search_results = self.search.search_and_group(search_query)

            if not search_results:
                result['error'] = "No documents found matching the query"
                result['steps'].append({
                    'step': 'search_documents',
                    'status': 'failed',
                })
                return result

            result['steps'].append({
                'step': 'search_documents',
                'status': 'success',
            })

            # Step 3: Select best document
            logger.info("Step 3: Selecting document")
            file_path = search_results[0]['file_path']
            file_name = search_results[0]['file_name']

            result['steps'].append({
                'step': 'select_document',
                'status': 'success',
                'data': {'file': file_name},
            })

            # Step 4: Extract content
            logger.info("Step 4: Extracting content")
            extraction_plan = self.planner.plan_section_extraction(
                document_metadata={'file_name': file_name},
                section_request=params.get('document_section', 'all'),
            )

            extracted_content = self.parser.extract_section(
                file_path, extraction_plan
            )

            if not extracted_content:
                result['error'] = "Failed to extract content from document"
                result['steps'].append({
                    'step': 'extract_content',
                    'status': 'failed',
                })
                return result

            result['steps'].append({
                'step': 'extract_content',
                'status': 'success',
            })

            # Step 5: Generate presentation structure
            logger.info("Step 5: Generating presentation structure")
            presentation_action = params.get('presentation_action', {})
            title = presentation_action.get('title', file_name)

            presentation_data = self.planner.generate_presentation(
                title=title, content=extracted_content
            )

            if not presentation_data:
                result['error'] = "Failed to generate presentation structure"
                result['steps'].append({
                    'step': 'generate_presentation',
                    'status': 'failed',
                })
                return result

            result['steps'].append({
                'step': 'generate_presentation',
                'status': 'success',
            })

            # Step 6: Create Keynote presentation
            logger.info("Step 6: Creating Keynote presentation")
            keynote_success = self.keynote_composer.create_presentation(
                title=presentation_data['title'],
                slides=presentation_data['slides'],
                output_path=presentation_action.get('output_path'),
            )

            if not keynote_success:
                result['error'] = "Failed to create Keynote presentation"
                result['steps'].append({
                    'step': 'create_keynote',
                    'status': 'failed',
                })
                return result

            result['steps'].append({
                'step': 'create_keynote',
                'status': 'success',
            })

            result['success'] = True
            result['summary'] = f"Created Keynote presentation '{presentation_data['title']}' with {len(presentation_data['slides'])} slides from '{file_name}'"

            return result

        except Exception as e:
            logger.error(f"Error in presentation workflow: {e}")
            result['error'] = str(e)
            return result

    def _execute_document_workflow(
        self, params: Dict[str, Any], result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute workflow for creating a Keynote presentation from document content.

        Args:
            params: Parameters from intent parsing
            result: Result dictionary to update

        Returns:
            Updated result dictionary
        """
        try:
            # Step 2: Search for document
            logger.info("Step 2: Searching for source document")
            search_query = params.get('search_query', '')
            search_results = self.search.search_and_group(search_query)

            if not search_results:
                result['error'] = "No documents found matching the query"
                result['steps'].append({
                    'step': 'search_documents',
                    'status': 'failed',
                })
                return result

            result['steps'].append({
                'step': 'search_documents',
                'status': 'success',
            })

            # Step 3: Select best document
            logger.info("Step 3: Selecting document")
            file_path = search_results[0]['file_path']
            file_name = search_results[0]['file_name']

            result['steps'].append({
                'step': 'select_document',
                'status': 'success',
                'data': {'file': file_name},
            })

            # Step 4: Extract content
            logger.info("Step 4: Extracting content")
            extraction_plan = self.planner.plan_section_extraction(
                document_metadata={'file_name': file_name},
                section_request=params.get('document_section', 'all'),
            )

            extracted_content = self.parser.extract_section(
                file_path, extraction_plan
            )

            if not extracted_content:
                result['error'] = "Failed to extract content from document"
                result['steps'].append({
                    'step': 'extract_content',
                    'status': 'failed',
                })
                return result

            result['steps'].append({
                'step': 'extract_content',
                'status': 'success',
            })

            # Step 5: Generate document structure
            logger.info("Step 5: Generating document structure")
            document_action = params.get('document_action', {})
            title = document_action.get('title', file_name)

            document_data = self.planner.generate_document(
                title=title, content=extracted_content
            )

            if not document_data:
                result['error'] = "Failed to generate document structure"
                result['steps'].append({
                    'step': 'generate_document',
                    'status': 'failed',
                })
                return result

            result['steps'].append({
                'step': 'generate_document',
                'status': 'success',
            })

            # Step 6: Create Keynote presentation
            logger.info("Step 6: Creating Keynote presentation")
            
            # Convert document sections to Keynote slides format
            slides = []
            for section in document_data.get('sections', []):
                slide_title = section.get('heading', '')
                slide_content = section.get('content', '')
                if slide_title or slide_content:
                    slides.append({
                        'title': slide_title or 'Content',
                        'content': slide_content
                    })
            
            # If no sections, create a single slide from the title and content
            if not slides:
                slides.append({
                    'title': document_data['title'],
                    'content': extracted_content[:1000]  # First 1000 chars as fallback
                })
            
            # Determine output path
            output_path = document_action.get('output_path')
            if not output_path:
                import os
                output_path = os.path.expanduser(f"~/Documents/{document_data['title']}.key")
            
            keynote_success = self.keynote_composer.create_presentation(
                title=document_data['title'],
                slides=slides,
                output_path=output_path,
            )

            if not keynote_success:
                result['error'] = "Failed to create Keynote presentation"
                result['steps'].append({
                    'step': 'create_keynote',
                    'status': 'failed',
                })
                return result

            result['steps'].append({
                'step': 'create_keynote',
                'status': 'success',
            })

            result['success'] = True
            result['summary'] = f"Created Keynote presentation '{document_data['title']}' with {len(slides)} slides from '{file_name}'"

            return result

        except Exception as e:
            logger.error(f"Error in document workflow: {e}")
            result['error'] = str(e)
            return result
