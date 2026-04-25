import os
import logging
import datetime
from typing import Any, Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger("genaudius-mcp-memory")

class MemoryEngine:
    """
    Motor de persistencia para el MCP. 
    Se encarga de memorizar interacciones y gestionar colecciones en MongoDB.
    """
    def __init__(self):
        self.mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        self.db_name = os.environ.get("MONGO_DB", "genaudius_mcp_memory")
        self.client = None
        self.db = None
        self.enabled = False

    async def connect(self):
        try:
            self.client = AsyncIOMotorClient(self.mongo_url)
            self.db = self.client[self.db_name]
            # Test connection
            await self.client.admin.command('ping')
            self.enabled = True
            logger.info(f"✅ Conectado a MongoDB: {self.db_name}")
        except Exception as e:
            logger.error(f"❌ Error al conectar a MongoDB: {e}")
            self.enabled = False

    async def log_interaction(self, user_id: str, tool_name: str, arguments: Dict[str, Any], result: Any):
        """Guarda una interacción con una herramienta."""
        if not self.enabled: return
        
        entry = {
            "user_id": user_id,
            "timestamp": datetime.datetime.utcnow(),
            "tool": tool_name,
            "arguments": arguments,
            "result_summary": str(result)[:500], # Resumen para no saturar
            "type": "interaction"
        }
        
        try:
            await self.db.interactions.insert_one(entry)
        except Exception as e:
            logger.error(f"Error guardando interacción: {e}")

    async def store_memory(self, user_id: str, category: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Guarda un recuerdo específico o dato importante del usuario."""
        if not self.enabled: return
        
        memory = {
            "user_id": user_id,
            "timestamp": datetime.datetime.utcnow(),
            "category": category,
            "content": content,
            "metadata": metadata or {},
            "type": "memory"
        }
        
        try:
            await self.db.memories.insert_one(memory)
            return True
        except Exception as e:
            logger.error(f"Error guardando memoria: {e}")
            return False

    async def get_recent_memories(self, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Recupera los recuerdos más recientes para dar contexto a la IA."""
        if not self.enabled: return []
        
        try:
            cursor = self.db.memories.find({"user_id": user_id}).sort("timestamp", -1).limit(limit)
            return await cursor.to_list(length=limit)
        except Exception as e:
            logger.error(f"Error recuperando memorias: {e}")
            return []

# Instancia global
memory_engine = MemoryEngine()
