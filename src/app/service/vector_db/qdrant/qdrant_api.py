from uuid import uuid4
from loguru import logger
from typing import Any, List

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    VectorParams,
    Distance,
    PointStruct,
    Filter,
    PointIdsList,
    FieldCondition,
    MatchAny,
    MatchValue,
)

from app.models.rag import SearchResponse, SearchPayload


class QdrantAPI:
    def __init__(self, url: str):
        """
        Initialize QdrantAPI with connection parameters and vector store settings.

        Args:
            url (str): URL of the Qdrant server
        """
        self.client = AsyncQdrantClient(url=url)

    async def create_collection(
        self,
        collection_name: str,
        vector_size: int,
        metadata: dict | None = None,
    ) -> None:
        """
        Create a Qdrant collection if it does not already exist.

        Args:
            collection_name (str): Name of the collection to create
            vector_size (int): Size of vectors for the collection
        """

        if not await self.client.collection_exists(collection_name=collection_name):
            await self.client.create_collection(
                collection_name=collection_name,
                metadata=metadata,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
            logger.info(
                "Created Qdrant collection: {collection_name}".format(
                    collection_name=collection_name
                )
            )
        else:
            logger.info(
                "Qdrant collection already exists: {collection_name}".format(
                    collection_name=collection_name
                )
            )

    async def delete_collection(self, collection_name: str) -> None:
        """
        Delete a Qdrant collection if it exists.

        Args:
            collection_name (str): Name of the collection to delete
        """
        if await self.client.collection_exists(collection_name=collection_name):
            await self.client.delete_collection(collection_name=collection_name)
            logger.info(
                "Deleted Qdrant collection: {collection_name}".format(
                    collection_name=collection_name
                )
            )
        else:
            logger.info(
                "Qdrant collection does not exist: {collection_name}".format(
                    collection_name=collection_name
                )
            )

    async def add_vectors(
        self,
        collection_name: str,
        vectors: List[List[float]],
        payloads: List[dict],
    ) -> None:
        """
        Add vectors to a Qdrant collection.

        Args:
            collection_name (str): Name of the collection to add vectors to
            vectors (List[List[float]]): List of vectors to add
            payloads (List[dict], optional): List of payloads for each vector
        """
        if not await self.client.collection_exists(collection_name=collection_name):
            raise ValueError(
                "Collection {collection_name} does not exist.".format(
                    collection_name=collection_name
                )
            )

        await self.client.upsert(
            collection_name=collection_name,
            points=[
                PointStruct(id=uuid4().hex, vector=vector, payload=payload)
                for vector, payload in zip(vectors, payloads)
            ],
        )

        logger.info(
            "Added {vectors} vectors to collection: {collection_name}".format(
                collection_name=collection_name, vectors=len(vectors)
            )
        )

    async def search(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int,
        file_ids: List[str] | None = None,
        score_threshold: float = 0.0,
    ) -> List[SearchResponse | None]:
        """
        Search for similar vectors in a Qdrant collection.

        Args:
            collection_name (str): Name of the collection to search
            query_vector (List[float]): The query vector
            limit (int): Number of similar vectors to return
            file_ids (List[str] | None): List of file IDs to filter by
            score_threshold (float): Minimum similarity score to consider

        Returns:
            List[FindSimilarDocsResponse | None]: List of search results with payloads and scores
        """
        if not await self.client.collection_exists(collection_name=collection_name):
            raise ValueError(
                "Collection {collection_name} does not exist.".format(
                    collection_name=collection_name
                )
            )

        query_filter = None

        if file_ids:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="file_id",
                        match=MatchAny(any=file_ids),  # file_id ∈ file_ids
                    )
                ]
            )

        search_results = await self.client.query_points(
            collection_name=collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            score_threshold=score_threshold,
            with_payload=True,
        )

        result = []

        if search_results:
            result = [
                SearchResponse(payload=SearchPayload(**res.payload), score=res.score)
                for res in search_results.points
            ]

        return result

    async def get_collections(self, filter: str | None = None) -> List[str | None]:
        """
        Retrieve the list of existing Qdrant collections.

        Args:
            filter (str, optional): Filter to apply when retrieving collections

        Returns:
            List[str]: List of collection names
        """

        collections = await self.client.get_collections()

        result = []
        if filter:
            result = [
                collection.name
                for collection in collections.collections
                if filter in collection.name
            ]
        else:
            result = [collection.name for collection in collections.collections]

        return result

    async def get_collection_metadata(self, collection_name: str) -> dict | None:
        """
        Retrieve metadata of a specific Qdrant collection.

        Args:
            collection_name (str): Name of the collection

        Returns:
            dict | None: Metadata of the collection or None if not found
        """

        if not await self.client.collection_exists(collection_name=collection_name):
            raise ValueError(
                "Collection {collection_name} does not exist.".format(
                    collection_name=collection_name
                )
            )

        collection = await self.client.get_collection(collection_name=collection_name)
        metadata = collection.config.metadata
        return metadata

    async def upsert_points(
        self,
        collection_name: str,
        points: list[dict[str, Any]],
    ) -> None:
        if not await self.client.collection_exists(collection_name=collection_name):
            raise ValueError(
                "Collection {collection_name} does not exist.".format(
                    collection_name=collection_name
                )
            )

        await self.client.upsert(
            collection_name=collection_name,
            points=[
                PointStruct(
                    id=point["id"],
                    vector=point["vector"],
                    payload=point["payload"],
                )
                for point in points
            ],
        )
        logger.info(
            "Upserted {points} points to collection: {collection_name}".format(
                points=len(points),
                collection_name=collection_name,
            )
        )

    async def search_points(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int,
        candidate_ids: list[str] | None = None,
        chunk_types: list[str] | None = None,
        score_threshold: float = 0.0,
    ) -> list[dict[str, Any]]:
        if not await self.client.collection_exists(collection_name=collection_name):
            raise ValueError(
                "Collection {collection_name} does not exist.".format(
                    collection_name=collection_name
                )
            )

        must_conditions = []
        if candidate_ids:
            must_conditions.append(
                FieldCondition(
                    key="candidate_id",
                    match=MatchAny(any=candidate_ids),
                )
            )
        if chunk_types:
            must_conditions.append(
                FieldCondition(
                    key="chunk_type",
                    match=MatchAny(any=chunk_types),
                )
            )

        query_filter = Filter(must=must_conditions) if must_conditions else None
        search_results = await self.client.query_points(
            collection_name=collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            score_threshold=score_threshold,
            with_payload=True,
        )
        return [
            {
                "id": str(point.id),
                "score": float(point.score),
                "payload": point.payload or {},
            }
            for point in search_results.points
        ]

    async def get_collection_distance_metric(
        self,
        collection_name: str,
    ) -> str | None:
        if not await self.client.collection_exists(collection_name=collection_name):
            raise ValueError(
                "Collection {collection_name} does not exist.".format(
                    collection_name=collection_name
                )
            )

        collection_info = await self.client.get_collection(collection_name=collection_name)
        vectors_config = getattr(collection_info.config.params, "vectors", None)
        if isinstance(vectors_config, dict):
            vectors_config = next(iter(vectors_config.values()), None)

        distance = getattr(vectors_config, "distance", None)
        if distance is None:
            return None
        return str(distance).split(".")[-1].lower()

    async def delete_vectors_by_file_id(
        self, collection_name: str, file_id: str
    ) -> None:
        """Delete all vectors that belong to a specific file inside a collection."""

        if not await self.client.collection_exists(collection_name=collection_name):
            raise ValueError(
                "Collection {collection_name} does not exist.".format(
                    collection_name=collection_name
                )
            )

        await self.client.delete(
            collection_name=collection_name,
            points_selector=Filter(  # remove all vectors with matching file_id
                must=[
                    FieldCondition(
                        key="file_id",
                        match=MatchValue(value=file_id),
                    )
                ]
            ),
        )

    async def delete_points_by_ids(
        self,
        collection_name: str,
        point_ids: list[str],
    ) -> None:
        if not point_ids:
            return
        if not await self.client.collection_exists(collection_name=collection_name):
            raise ValueError(
                "Collection {collection_name} does not exist.".format(
                    collection_name=collection_name
                )
            )
        await self.client.delete(
            collection_name=collection_name,
            points_selector=PointIdsList(points=point_ids),
        )

        logger.info(
            "Deleted vectors for file_id: {file_id} from collection: {collection_name}".format(
                file_id=file_id,
                collection_name=collection_name,
            )
        )

    async def delete_vectors_by_document_id(
        self,
        collection_name: str,
        document_id: str,
    ) -> None:
        if not await self.client.collection_exists(collection_name=collection_name):
            raise ValueError(
                "Collection {collection_name} does not exist.".format(
                    collection_name=collection_name
                )
            )

        await self.client.delete(
            collection_name=collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id),
                    )
                ]
            ),
        )
        logger.info(
            "Deleted vectors for document_id: {document_id} from collection: {collection_name}".format(
                document_id=document_id,
                collection_name=collection_name,
            )
        )
