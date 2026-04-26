
from __future__ import annotations


import json
import boto3
from typing import List, Dict, Any

from dotenv import load_dotenv
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from log_utils.logger import get_logger

load_dotenv()

logger = get_logger(__name__)

class LambdaTranslationClient:
    """Client for calling Lambda translation service."""
    
    def __init__(self, function_name: str = "InvoiceTranslatorFunction", region: str = "ap-south-1"):
        """
        Initialize Lambda translation client.
        
        Args:
            function_name: Name of your Lambda function
            region: AWS region where Lambda is deployed
        """
        self.function_name = function_name
        self.lambda_client = boto3.client('lambda', region_name=region)
        logger.info("[aws_translate_service][LambdaTranslationClient.__init__] Initialized — function='%s', region='%s'", function_name, region)
    
    def _invoke_lambda(self, payload: dict) -> dict:
        """Internal method to invoke Lambda function."""
        logger.debug("[aws_translate_service][LambdaTranslationClient._invoke_lambda] Invoking Lambda '%s' with payload keys: %s",
                     self.function_name, list(payload.keys()))
        try:
            response = self.lambda_client.invoke(
                FunctionName=self.function_name,
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )
            
            result = json.loads(response['Payload'].read())

            # Lambda unhandled crash — AWS wraps it without statusCode
            if 'errorMessage' in result:
                error_msg = result.get('errorMessage', 'Unknown Lambda error')
                error_type = result.get('errorType', '')
                logger.error("[aws_translate_service][LambdaTranslationClient._invoke_lambda] Lambda crashed — %s: %s", error_type, error_msg)
                raise Exception(f"Lambda crashed ({error_type}): {error_msg}")

            if result.get('statusCode') != 200:
                try:
                    error = json.loads(result.get('body', '{}')).get('error', repr(result))
                except Exception:
                    error = repr(result)
                logger.error("[aws_translate_service][LambdaTranslationClient._invoke_lambda] Lambda returned non-200 status — error: %s", error)
                raise Exception(f"Lambda translation failed: {error}")
            
            logger.debug("[aws_translate_service][LambdaTranslationClient._invoke_lambda] Lambda invocation successful")
            return json.loads(result['body'])
        
        except Exception as e:
            logger.error("[aws_translate_service][LambdaTranslationClient._invoke_lambda] Failed to invoke Lambda '%s': %s",
                         self.function_name, e, exc_info=True)
            raise
    
    def translate_text(self, text: str, source_language: str) -> str:
        """
        Translate a single text to English.
        
        Args:
            text: Text to translate
            source_language: Source language (e.g., "Vietnamese", "vi")
            
        Returns:
            Translated text in English
        """
        if not text or len(text.strip()) == 0:
            logger.debug("[aws_translate_service][LambdaTranslationClient.translate_text] Empty text received — returning empty string")
            return ""
        
        logger.info("[aws_translate_service][LambdaTranslationClient.translate_text] Translating text (len=%d) from lang='%s'",
                    len(text), source_language)
        payload = {
            "text": text,
            "source_language": source_language
        }
        
        result = self._invoke_lambda(payload)
        logger.debug("[aws_translate_service][LambdaTranslationClient.translate_text] Translation successful (result_len=%d)", len(result.get('translated_text', '')))
        return result['translated_text']
    
    def translate_batch(self, texts: List[str], source_language: str) -> List[str]:
        """
        Translate multiple texts to English.
        
        Args:
            texts: List of texts to translate
            source_language: Source language
            
        Returns:
            List of translated texts in English
        """
        if not texts:
            logger.debug("[aws_translate_service][LambdaTranslationClient.translate_batch] Empty texts list — returning empty list")
            return []
        
        logger.info("[aws_translate_service][LambdaTranslationClient.translate_batch] Translating batch of %d text(s) from lang='%s'",
                    len(texts), source_language)
        payload = {
            "texts": texts,
            "source_language": source_language
        }
        
        result = self._invoke_lambda(payload)
        translated = result['translated_texts']
        logger.debug("[aws_translate_service][LambdaTranslationClient.translate_batch] Batch translation successful — %d result(s)", len(translated))
        return translated
    
    def translate_line_items(self, line_items: List[Dict[str, Any]], source_language: str) -> List[Dict[str, Any]]:
        """
        Translate line item descriptions to English.
        
        Args:
            line_items: List of line items with 'description' field
            source_language: Source language
            
        Returns:
            List of line items with descriptions translated to English
        """
        if not line_items:
            logger.debug("[aws_translate_service][LambdaTranslationClient.translate_line_items] Empty line_items — returning empty list")
            return []
        
        logger.info("[aws_translate_service][LambdaTranslationClient.translate_line_items] Translating %d line item(s) from lang='%s'",
                    len(line_items), source_language)
        payload = {
            "line_items": line_items,
            "source_language": source_language
        }
        
        result = self._invoke_lambda(payload)
        translated = result['line_items']
        logger.debug("[aws_translate_service][LambdaTranslationClient.translate_line_items] Translation successful — %d item(s) returned", len(translated))
        return translated

    def translate_metadata(self, metadata: Dict[str, Any], source_language: str) -> Dict[str, Any]:
        """
        Translate metadata dict string values to English (Mode 4).

        Args:
            metadata: Dict of metadata fields
            source_language: Source language

        Returns:
            Dict with all string values translated to English
        """
        if not metadata:
            logger.debug("[aws_translate_service][LambdaTranslationClient.translate_metadata] Empty metadata — returning empty dict")
            return {}

        logger.info("[aws_translate_service][LambdaTranslationClient.translate_metadata] Translating metadata (%d key(s)) from lang='%s'",
                    len(metadata), source_language)
        payload = {
            "metadata": metadata,
            "source_language": source_language
        }

        result = self._invoke_lambda(payload)
        translated = result['metadata']
        logger.debug("[aws_translate_service][LambdaTranslationClient.translate_metadata] Translation successful — %d key(s) returned", len(translated))
        return translated
