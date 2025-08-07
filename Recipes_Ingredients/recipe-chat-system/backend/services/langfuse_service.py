# backend/services/langfuse_service.py
"""
Langfuse Service for LLM Observability.
Works with or without Langfuse - graceful degradation to logging.
"""
import logging
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
from functools import wraps
import time
from datetime import datetime
import os

from config import settings

logger = logging.getLogger(__name__)

# Try to import Langfuse, but work without it
LANGFUSE_AVAILABLE = False
try:
    from langfuse import Langfuse
    LANGFUSE_AVAILABLE = True
except ImportError:
    logger.info("Langfuse package not installed - observability features disabled")


class LangfuseService:
    """Service for managing Langfuse observability with graceful degradation."""
    
    def __init__(self):
        """Initialize Langfuse client if possible, otherwise run without it."""
        self.enabled = False
        self.client = None
        self.current_trace = None
        
        # FIX: Better handling of LANGFUSE_ENABLED environment variable
        langfuse_enabled_str = os.getenv("LANGFUSE_ENABLED", "false").lower()
        langfuse_enabled = langfuse_enabled_str in ("true", "1", "yes", "on")
        
        logger.info(f"LANGFUSE_ENABLED env var: '{os.getenv('LANGFUSE_ENABLED')}' -> parsed as {langfuse_enabled}")
        
        # Check if Langfuse should be enabled
        if not langfuse_enabled:
            logger.info("Langfuse disabled by configuration (LANGFUSE_ENABLED=false)")
            return
        
        if not LANGFUSE_AVAILABLE:
            logger.warning("Langfuse package not available - install langfuse to enable observability")
            return
        
        # Check for API keys
        public_key = settings.LANGFUSE_PUBLIC_KEY or os.getenv("LANGFUSE_PUBLIC_KEY")
        secret_key = settings.LANGFUSE_SECRET_KEY or os.getenv("LANGFUSE_SECRET_KEY")
        
        # FIX: Better host resolution for Docker networking
        langfuse_host = os.getenv("LANGFUSE_HOST", settings.LANGFUSE_HOST)
        
        logger.info(f"Attempting to connect to Langfuse at: {langfuse_host}")
        
        if not public_key or not secret_key:
            logger.info(
                "Langfuse API keys not configured. System running without observability. "
                "To enable: Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY in .env"
            )
            return
        
        # Try to initialize Langfuse
        try:
            self.client = Langfuse(
                host=langfuse_host,
                public_key=public_key,
                secret_key=secret_key,
                flush_at=1,  # Send immediately
                flush_interval=1,  # Check every second
                max_retries=3,
                timeout=10,
                enabled=True,
                sdk_integration="recipe-chat-system"  # Add SDK integration name
            )
            self.enabled = True
            logger.info(f"✅ Langfuse observability enabled: {langfuse_host}")
            
            # Test the connection
            if self.test_connection():
                logger.info("✅ Langfuse connection verified")
            else:
                logger.warning("⚠️ Langfuse initialized but connection test failed")
            
        except Exception as e:
            logger.warning(f"Could not initialize Langfuse: {e}. Running without observability.")
            self.enabled = False
            self.client = None
    
    def test_connection(self):
        """Test if Langfuse is accessible."""
        if not self.enabled or not self.client:
            return False
        
        try:
            trace = self.client.trace(
                name="connection_test",
                metadata={"test": True, "timestamp": datetime.now().isoformat()}
            )
            self.client.flush()
            logger.debug(f"Langfuse connection test successful - trace id: {trace.id}")
            return True
        except Exception as e:
            logger.debug(f"Langfuse connection test failed: {e}")
            return False
    
    def start_trace(self, name: str, user_id: Optional[int] = None, 
                   conversation_id: Optional[int] = None, 
                   metadata: Optional[Dict] = None) -> Optional[Any]:
        """Start a new trace if Langfuse is enabled."""
        if not self.enabled or not self.client:
            # Just log if Langfuse not available
            logger.debug(f"[TRACE START] {name} - user:{user_id} conversation:{conversation_id}")
            return None
        
        try:
            trace_metadata = {
                "environment": settings.LANGFUSE_ENVIRONMENT,
                "app_version": settings.APP_VERSION,
            }
            if metadata:
                trace_metadata.update(metadata)
            
            self.current_trace = self.client.trace(
                name=name,
                user_id=str(user_id) if user_id else None,
                session_id=str(conversation_id) if conversation_id else None,
                metadata=trace_metadata,
                tags=[settings.LANGFUSE_ENVIRONMENT, "recipe-chat"]
            )
            logger.debug(f"Started Langfuse trace: {self.current_trace.id}")
            return self.current_trace
            
        except Exception as e:
            logger.debug(f"Could not start trace: {e}")
            return None
    
    def track_generation(self, 
                        name: str,
                        model: str,
                        prompt: str,
                        completion: str,
                        metadata: Optional[Dict] = None,
                        usage: Optional[Dict] = None,
                        latency: Optional[float] = None) -> Optional[Any]:
        """Track an LLM generation if Langfuse is enabled."""
        if not self.enabled or not self.client:
            # Just log the operation
            logger.info(f"[LLM] {name} - model:{model} latency:{latency:.2f}s" if latency else f"[LLM] {name} - model:{model}")
            return None
        
        try:
            generation_metadata = {
                "model": model,
                "temperature": 0.0,
            }
            if metadata:
                generation_metadata.update(metadata)
            
            if self.current_trace:
                generation = self.current_trace.generation(
                    name=name,
                    model=model,
                    input=prompt,
                    output=completion,
                    metadata=generation_metadata,
                    usage=usage,
                    latency=latency
                )
            else:
                generation = self.client.generation(
                    name=name,
                    model=model,
                    input=prompt,
                    output=completion,
                    metadata=generation_metadata,
                    usage=usage,
                    latency=latency
                )
            
            self.client.flush()
            logger.debug(f"Tracked generation in Langfuse: {name}")
            return generation
            
        except Exception as e:
            logger.debug(f"Could not track generation: {e}")
            return None
    
    def track_span(self, 
                   name: str,
                   metadata: Optional[Dict] = None,
                   input: Optional[Any] = None,
                   output: Optional[Any] = None,
                   level: str = "DEFAULT") -> Optional[Any]:
        """Track a span if Langfuse is enabled."""
        if not self.enabled or not self.client:
            logger.debug(f"[SPAN] {name}")
            return None
        
        try:
            if self.current_trace:
                span = self.current_trace.span(
                    name=name,
                    metadata=metadata,
                    input=input,
                    output=output,
                    level=level
                )
            else:
                span = self.client.span(
                    name=name,
                    metadata=metadata,
                    input=input,
                    output=output,
                    level=level
                )
            logger.debug(f"Tracked span in Langfuse: {name}")
            return span
            
        except Exception as e:
            logger.debug(f"Could not track span: {e}")
            return None
    
    @contextmanager
    def span_context(self, name: str, metadata: Optional[Dict] = None):
        """Context manager for tracking spans."""
        span = None
        start_time = time.time()
        
        try:
            if self.enabled and self.client:
                span = self.track_span(name=name, metadata=metadata)
            else:
                logger.debug(f"[SPAN START] {name}")
            
            yield span
            
        finally:
            latency = time.time() - start_time
            if span:
                try:
                    span.update(
                        metadata={**(metadata or {}), "latency_seconds": latency}
                    )
                except Exception as e:
                    logger.debug(f"Could not update span: {e}")
            else:
                logger.debug(f"[SPAN END] {name} - {latency:.2f}s")
    
    def track_score(self,
                   name: str,
                   value: float,
                   trace_id: Optional[str] = None,
                   observation_id: Optional[str] = None,
                   comment: Optional[str] = None) -> None:
        """Track a score if Langfuse is enabled."""
        if not self.enabled or not self.client:
            logger.debug(f"[SCORE] {name}={value}")
            return
        
        try:
            self.client.score(
                name=name,
                value=value,
                trace_id=trace_id,
                observation_id=observation_id,
                comment=comment
            )
            self.client.flush()
            logger.debug(f"Tracked score in Langfuse: {name}={value}")
        except Exception as e:
            logger.debug(f"Could not track score: {e}")
    
    def flush(self):
        """Flush any pending data to Langfuse."""
        if self.enabled and self.client:
            try:
                self.client.flush()
                logger.debug("Flushed Langfuse data")
            except Exception as e:
                logger.debug(f"Could not flush Langfuse: {e}")
    
    def shutdown(self):
        """Shutdown Langfuse client."""
        if self.enabled and self.client:
            try:
                self.flush()
                self.client.shutdown()
                logger.info("Langfuse client shutdown")
            except Exception as e:
                logger.debug(f"Error during Langfuse shutdown: {e}")


def langfuse_trace(name: str = None, **decorator_kwargs):
    """
    Decorator for tracing functions with Langfuse.
    Works even if Langfuse is not available.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            service = get_langfuse_service()
            
            if not service.enabled:
                # Just run the function without tracing
                return func(*args, **kwargs)
            
            trace_name = name or func.__name__
            start_time = time.time()
            
            # Start span
            span = service.track_span(
                name=trace_name,
                metadata=decorator_kwargs,
                input={"args": str(args)[:500], "kwargs": str(kwargs)[:500]}
            )
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                
                # Update span with output
                if span:
                    latency = time.time() - start_time
                    span.update(
                        output=str(result)[:500],
                        metadata={**decorator_kwargs, "latency_seconds": latency}
                    )
                
                return result
                
            except Exception as e:
                # Track error
                if span:
                    span.update(
                        metadata={**decorator_kwargs, "error": str(e)},
                        level="ERROR"
                    )
                raise
        
        return wrapper
    return decorator


# Singleton instance
_langfuse_service: Optional[LangfuseService] = None

def get_langfuse_service() -> LangfuseService:
    """Get or create singleton Langfuse service instance."""
    global _langfuse_service
    if _langfuse_service is None:
        _langfuse_service = LangfuseService()
    return _langfuse_service