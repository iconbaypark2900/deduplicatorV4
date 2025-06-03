#!/usr/bin/env python3
"""
Command-line interface for the PDF deduplication system.
Provides a unified entry point for all workflows.
"""

import argparse
import os
import sys
import logging
from typing import List, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("pdf-deduplicator.log"),
    ]
)
logger = logging.getLogger(__name__)

# Import workflow modules
from cli.doc_comparator import compare_documents_workflow
from cli.batch_folder import batch_folder_check
from cli.intra_doc_inspector import inspect_intra_document

# Import Celery tasks for CLI triggers
try:
    from backend.tasks.vectorizer_tasks import manage_tfidf_vectorizer_task
    # Import other tasks if they need CLI triggers, e.g.:
    # from backend.tasks.lsh_tasks import rebuild_global_lsh_index_task
except ImportError as e:
    logger.warning(f"Could not import Celery tasks for CLI: {e}. Task-triggering CLI commands may not work.")
    manage_tfidf_vectorizer_task = None


def setup_parser() -> argparse.ArgumentParser:
    """
    Set up the command-line argument parser.
    
    Returns:
        Configured argument parser
    """
    parser = argparse.ArgumentParser(
        description="Medical PDF Deduplication System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Compare two documents
  pdf-dedupe compare file1.pdf file2.pdf
  
  # Analyze a batch folder
  pdf-dedupe batch folder_path
  
  # Analyze a single document for internal duplicates
  pdf-dedupe inspect document.pdf
  
  # Start the web server
  pdf-dedupe server
  
  # Manage TF-IDF Vectorizer
  pdf-dedupe manage-vectorizer
  pdf-dedupe manage-vectorizer --force-refit
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare two documents")
    compare_parser.add_argument("file1", help="First PDF file")
    compare_parser.add_argument("file2", help="Second PDF file")
    compare_parser.add_argument("--threshold", type=float, default=0.85,
                               help="Similarity threshold (0-1)")
    
    # Batch command
    batch_parser = subparsers.add_parser("batch", help="Analyze a batch folder")
    batch_parser.add_argument("folder", help="Folder containing PDFs")
    batch_parser.add_argument("--output", help="Output folder for results")
    batch_parser.add_argument("--threshold", type=float, default=0.9,
                             help="Similarity threshold (0-1)")
    
    # Inspect command
    inspect_parser = subparsers.add_parser("inspect", help="Analyze a single document")
    inspect_parser.add_argument("document", help="PDF document to analyze")
    inspect_parser.add_argument("--threshold", type=float, default=0.85,
                               help="Page similarity threshold (0-1)")
    
    # Server command
    server_parser = subparsers.add_parser("server", help="Start the web server")
    server_parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    server_parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    server_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    
    # Manage Vectorizer command
    vectorizer_parser = subparsers.add_parser("manage-vectorizer", help="Manage the TF-IDF vectorizer (fit/refit and update document vectors)")
    vectorizer_parser.add_argument("--force-refit", action="store_true", default=False,
                               help="Force refitting the vectorizer even if one exists. Default: False.")
    
    return parser


def validate_args(args: argparse.Namespace) -> bool:
    """
    Validate command-line arguments.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        True if arguments are valid, False otherwise
    """
    if args.command == "compare":
        if not os.path.isfile(args.file1):
            logger.error(f"File not found: {args.file1}")
            return False
        if not os.path.isfile(args.file2):
            logger.error(f"File not found: {args.file2}")
            return False
    
    elif args.command == "batch":
        if not os.path.isdir(args.folder):
            logger.error(f"Folder not found: {args.folder}")
            return False
    
    elif args.command == "inspect":
        if not os.path.isfile(args.document):
            logger.error(f"Document not found: {args.document}")
            return False
    
    elif args.command == "manage-vectorizer":
        # No specific validation needed for manage-vectorizer beyond argparse handling the boolean flag
        return True
    
    return True


def run_command(args: argparse.Namespace) -> int:
    """
    Run the specified command.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    if args.command == "compare":
        return compare_documents_workflow(args.file1, args.file2, args.threshold)
    
    elif args.command == "batch":
        return batch_folder_check(args.folder, args.threshold, args.output)
    
    elif args.command == "inspect":
        return inspect_intra_document(args.document, args.threshold)
    
    elif args.command == "server":
        import uvicorn
        from backend.main import app
        
        logger.info(f"Starting server on {args.host}:{args.port}")
        uvicorn.run(
            "backend.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload
        )
        return 0
    
    elif args.command == "manage-vectorizer":
        if manage_tfidf_vectorizer_task:
            logger.info(f"Triggering TF-IDF vectorizer management task with force_refit={args.force_refit}...")
            try:
                # Using .delay() as a shortcut for .apply_async() with default options
                manage_tfidf_vectorizer_task.delay(force_refit=args.force_refit)
                logger.info("Task successfully queued. Check Celery worker logs for progress.")
                return 0
            except Exception as e:
                logger.error(f"Failed to queue TF-IDF vectorizer management task: {e}", exc_info=True)
                return 1
        else:
            logger.error("manage_tfidf_vectorizer_task is not available. Ensure Celery and its tasks are correctly configured.")
            return 1
    
    else:
        logger.error(f"Unknown command: {args.command}")
        return 1


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main entry point for the CLI.
    
    Args:
        argv: Command-line arguments
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = setup_parser()
    
    if argv is None:
        args = parser.parse_args()
    else:
        args = parser.parse_args(argv)
    
    if not args.command:
        parser.print_help()
        return 0
    
    if not validate_args(args):
        return 1
    
    try:
        return run_command(args)
    except Exception as e:
        logger.exception(f"Error running command: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())