"""
Servicio principal para manejo del feed social con embeddings y recomendaciones
"""

import logging
from typing import Any

import requests
from django.conf import settings
from django.db import models
from django.db.models import Count, F, Q
from django.db.models.expressions import RawSQL

# Importar servicio de vectores de usuario
from apps.custom_auth.domain.services.user_vector_service import user_vector_service
from apps.custom_auth.identity_principal import (
    ref_from_snapshot,
    snapshot_from_principal,
)
from apps.feeds.domain.entities.comment import Comment

# Importar modelos del feed
from apps.feeds.domain.entities.feed_post import FeedPost
from apps.feeds.domain.entities.like import Like

logger = logging.getLogger(__name__)


class FeedService:
    """
    Servicio principal para manejo del feed social
    """

    def __init__(self, embedding_service_url: str = None):
        self.embedding_service_url = (
            embedding_service_url or settings.EMBEDDING_SERVICE_URL
        )

    def get_embedding_from_microservice(self, text: str) -> list[float] | None:
        """
        Obtiene embedding de texto desde el microservicio
        """
        try:
            payload = {"text": text, "translate_to_english": True, "clean_text": True}

            response = requests.post(
                f"{self.embedding_service_url}/text-processing/vectorize/",
                json=payload,
                timeout=30,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                result = response.json()
                vector = result.get("vector")
                if vector:
                    logger.info(
                        f"Embedding generado para post. "
                        f"Dimensiones: {result.get('dimension', len(vector))}"
                    )
                    return vector
                else:
                    logger.error("El microservicio no devolvió un vector válido")
                    return None
            else:
                logger.error(
                    f"Error al obtener embedding: {response.status_code} - "
                    f"{response.text}"
                )
                return None

        except requests.RequestException as e:
            logger.error(f"Error de conexión con microservicio: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado: {str(e)}")
            return None

    def create_post(
        self,
        author=None,
        author_id: str = None,
        content: str = None,
        tags: list[str] = None,
        files: list[dict] = None,
        is_public: bool = True,
    ) -> FeedPost | None:
        """
        Crea un nuevo post en el feed

        Args:
            author: Instancia del usuario autor (alternativo a author_id)
            author_id: ID del autor (alternativo a author)
            content: Contenido del post
            tags: Lista de tags
            files: Lista de archivos del post
            is_public: Si el post es público

        Returns:
            Instancia del post creado o None si hay error
        """
        try:
            if author:
                author_id = str(author.id)
            elif author_id:
                author = ref_from_snapshot(str(author_id), {"id": str(author_id)})
            else:
                raise ValueError("Debe proporcionar author o author_id")

            post = FeedPost.objects.create(
                author_identity_id=str(author_id),
                author_snapshot=snapshot_from_principal(author),
                content=content,
                tags=tags or [],
                is_public=is_public,
            )

            # Generar embedding para el post
            self.update_post_embedding(post.id)

            # Actualizar vectores del usuario basado en su nuevo post
            user_vector_service.update_user_vectors_on_interaction(
                user_id=author_id, interaction_type="post_created", content=content
            )

            logger.info(f"Post creado: {post.id} por {author_id}")
            return post

        except Exception as e:
            logger.error(f"Error creando post: {str(e)}")
            return None

    def update_post_embedding(self, post_id: str) -> bool:
        """
        Actualiza el embedding de un post
        """
        try:
            post = FeedPost.objects.get(id=post_id)

            # Generar texto para embedding
            embedding_text = self._generate_post_embedding_text(post)

            # Obtener embedding
            embedding = self.get_embedding_from_microservice(embedding_text)

            if embedding:
                post.embedding = embedding
                post.save(update_fields=["embedding"])
                logger.info(f"Embedding actualizado para post {post_id}")
                return True
            else:
                logger.error(f"No se pudo generar embedding para post {post_id}")
                return False

        except FeedPost.DoesNotExist:
            logger.error(f"Post {post_id} no encontrado")
            return False
        except Exception as e:
            logger.error(f"Error actualizando embedding: {str(e)}")
            return False

    def _generate_post_embedding_text(self, post: FeedPost) -> str:
        """
        Genera texto completo del post para crear embedding
        """
        text_parts = [post.content]

        # Agregar tags
        if post.tags:
            text_parts.append("Tags: " + ", ".join(post.tags))

        # Agregar información del autor
        author_name = (
            post.author.get_full_name()
            or post.author.username
            or post.author_identity_id
        )
        text_parts.append(f"Autor: {author_name}")
        investigation_camp = post.author_snapshot.get("investigation_camp")
        if investigation_camp:
            text_parts.append(f"Campo: {investigation_camp}")

        return ". ".join(text_parts)

    def get_personalized_feed(
        self, user_id: str = None, user=None, limit: int = 20, cursor: str = None
    ):
        """
        Obtiene feed personalizado basado en el embedding del usuario
        """
        try:
            if user:
                user_id = str(user.id)

            logger.info(f"Obteniendo feed personalizado para usuario {user_id}")

            # La identidad canonica ya no vive en social_consensus_backend. Mientras
            # profile_identity_backend expone embeddings/perfil de intereses por API,
            # se evita consultar tablas locales de usuario y se usa feed trending.
            return self.get_trending_feed(limit, cursor, exclude_user_id=user_id)

        except Exception as e:
            logger.error(f"Error obteniendo feed personalizado: {str(e)}")
            import traceback

            logger.error(traceback.format_exc())
            return self.get_trending_feed(limit, cursor, exclude_user_id=user_id)

    def get_trending_feed(
        self, limit: int = 20, cursor: str = None, exclude_user_id: str = None
    ):
        """
        Obtiene posts en tendencia basados en engagement
        """
        try:
            logger.info(f"Obteniendo feed trending con límite: {limit}")

            hours_old_sql = (
                'EXTRACT(EPOCH FROM (NOW() - "feeds_feedpost"."created_at")) / 3600'
            )

            # Nuevo algoritmo de trending mejorado:
            # 1. Usa el engagement_score ya calculado que incluye el decaimiento
            #    logarítmico
            # 2. Agrega un boost para posts con alta velocidad de engagement reciente
            trending_score_sql = f"""
                (
                    engagement_score * 0.8 + 
                    (engagement_score / SQRT(GREATEST(1, {hours_old_sql}))) * 0.2
                )
            """

            queryset = FeedPost.objects.filter(is_public=True)

            # Excluir posts propios del usuario si se especifica
            if exclude_user_id:
                queryset = queryset.exclude(author_identity_id=str(exclude_user_id))

            queryset = (
                queryset.annotate(
                    hours_old=RawSQL(hours_old_sql, []),
                    trending_score=RawSQL(trending_score_sql, []),
                    comments_count_real=Count(
                        "comments", filter=models.Q(comments__is_deleted=False)
                    ),
                )
                .prefetch_related("post_files", "comments")
                .order_by("-trending_score")
            )

            # Contar posts disponibles
            total_count = queryset.count()
            logger.info(f"Posts públicos disponibles para trending: {total_count}")

            # Aplicar cursor si se proporciona
            if cursor:
                queryset = queryset.filter(created_at__lt=cursor)

            posts = list(queryset[: limit + 1])  # +1 to check if there's more

            # Si no hay posts con engagement score, obtener los más recientes
            if not posts:
                logger.info("No hay posts trending, obteniendo los más recientes")
                return self.get_latest_feed(
                    limit, cursor, exclude_user_id=exclude_user_id
                )

            has_next = len(posts) > limit

            if has_next:
                posts = posts[:limit]
                next_cursor = posts[-1].created_at.isoformat() if posts else None
            else:
                next_cursor = None

            logger.info(f"Feed trending obtenido: {len(posts)} posts")
            return posts, has_next, next_cursor

        except Exception as e:
            logger.error(f"Error obteniendo feed trending: {str(e)}")
            import traceback

            logger.error(traceback.format_exc())
            return self.get_latest_feed(limit, cursor, exclude_user_id=exclude_user_id)

    def handle_user_interaction(
        self, user_id: str, post_id: str, interaction_type: str
    ):
        """
        Maneja interacciones del usuario con posts (view, like, comment, share)
        """
        try:
            post = FeedPost.objects.get(id=post_id)

            # Actualizar métricas del post
            if interaction_type == "view":
                post.views_count = F("views_count") + 1
            elif interaction_type == "share":
                post.shares_count = F("shares_count") + 1

            if interaction_type in ["view", "share"]:
                post.save(update_fields=[f"{interaction_type}s_count"])
                post.refresh_from_db()
                post.update_engagement_score()

            # Actualizar vectores del usuario basado en la interacción
            user_vector_service.update_user_vectors_on_interaction(
                user_id=user_id,
                interaction_type=interaction_type,
                content=post.content[:200],  # Primeros 200 caracteres
            )

            logger.info(
                f"Interacción {interaction_type} registrada: Usuario {user_id} - "
                f"Post {post_id}"
            )

        except FeedPost.DoesNotExist:
            logger.error(f"Post {post_id} no encontrado")
        except Exception as e:
            logger.error(f"Error manejando interacción: {str(e)}")

    def create_comment(
        self,
        author_id: str,
        post_id: str,
        content: str,
        parent_comment_id: str = None,
        author_snapshot: dict = None,
    ) -> Comment | None:
        """
        Crea un comentario en un post
        """
        try:
            post = FeedPost.objects.get(id=post_id)

            parent_comment = None
            if parent_comment_id:
                parent_comment = Comment.objects.get(id=parent_comment_id)

                # Verificar límite de anidación
                if not parent_comment.can_reply():
                    logger.warning(
                        f"Máximo nivel de anidación alcanzado para comentario "
                        f"{parent_comment_id}"
                    )
                    return None

            # Crear comentario
            comment = Comment.objects.create(
                post=post,
                author_identity_id=str(author_id),
                author_snapshot=author_snapshot or {"id": str(author_id)},
                parent_comment=parent_comment,
                content=content,
            )

            # Actualizar engagement del post
            post.update_engagement_score()
            # Actualizar vectores del usuario
            user_vector_service.update_user_vectors_on_interaction(
                user_id=author_id, interaction_type="comment", content=content
            )

            logger.info(f"Comentario creado: {comment.id} por {author_id}")
            return comment

        except (FeedPost.DoesNotExist, Comment.DoesNotExist) as e:
            logger.error(f"Objeto no encontrado: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error creando comentario: {str(e)}")
            return None

    def toggle_like(self, user, post):
        """
        Alterna like en post específico
        """
        try:
            # Toggle like
            like, created = Like.toggle_like(user, post)

            # Actualizar engagement del post
            post.update_engagement_score()

            # Actualizar vectores del usuario si se creó el like
            if created:
                user_vector_service.update_user_vectors_on_interaction(
                    user_id=user.id, interaction_type="like", content=post.content[:100]
                )

            logger.info(
                f"Like {'creado' if created else 'eliminado'}: Usuario {user.id} - "
                f"Post {post.id}"
            )
            return created  # Return True if liked, False if unliked

        except Exception as e:
            logger.error(f"Error toggleando like en post: {str(e)}")
            return False

    def get_latest_feed(
        self, limit: int = 20, cursor: str = None, exclude_user_id: str = None
    ):
        """
        Obtiene feed con posts más recientes
        """
        try:
            logger.info(f"Obteniendo feed más reciente con límite: {limit}")

            queryset = FeedPost.objects.filter(is_public=True)

            # Excluir posts propios del usuario si se especifica
            if exclude_user_id:
                queryset = queryset.exclude(author_identity_id=str(exclude_user_id))

            queryset = queryset.order_by("-created_at")

            # Contar posts disponibles
            total_count = queryset.count()
            logger.info(f"Posts públicos más recientes disponibles: {total_count}")

            if cursor:
                # Cursor-based pagination
                queryset = queryset.filter(created_at__lt=cursor)

            posts = list(queryset[: limit + 1])  # +1 to check if there's more
            has_next = len(posts) > limit

            if has_next:
                posts = posts[:limit]
                next_cursor = posts[-1].created_at.isoformat() if posts else None
            else:
                next_cursor = None

            logger.info(f"Feed más reciente obtenido: {len(posts)} posts")
            return posts, has_next, next_cursor

        except Exception as e:
            logger.error(f"Error obteniendo feed reciente: {str(e)}")
            return [], False, None

    def get_filtered_feed(
        self,
        user,
        feed_type: str,
        filters: dict[str, Any],
        limit: int = 20,
        cursor: str = None,
    ):
        """
        Obtiene feed filtrado según criterios
        """
        try:
            # Start with base feed
            if feed_type == "personalized":
                posts, _, _ = self.get_personalized_feed(
                    user=user, limit=limit * 2, cursor=cursor
                )
                queryset = FeedPost.objects.filter(id__in=[p.id for p in posts])
            elif feed_type == "trending":
                user_id = user.id if user else None
                posts, _, _ = self.get_trending_feed(
                    limit * 2, cursor, exclude_user_id=user_id
                )
                queryset = FeedPost.objects.filter(id__in=[p.id for p in posts])
            else:
                queryset = FeedPost.objects.filter(is_public=True)

            # Apply filters
            if filters.get("tags"):
                # `tags` es un JSONField (no ArrayField): "__overlap" no es un
                # lookup valido ahi y termina interpretandose como una clave
                # JSON inexistente, devolviendo siempre 0 resultados. Un OR de
                # "__contains" por tag replica la semantica de "cualquiera".
                tags_query = Q()
                for tag in filters["tags"]:
                    tags_query |= Q(tags__contains=[tag])
                queryset = queryset.filter(tags_query)

            if filters.get("author_ids"):
                queryset = queryset.filter(
                    author_identity_id__in=[
                        str(author_id) for author_id in filters["author_ids"]
                    ]
                )

            if filters.get("date_from"):
                queryset = queryset.filter(created_at__gte=filters["date_from"])

            if filters.get("date_to"):
                queryset = queryset.filter(created_at__lte=filters["date_to"])

            if filters.get("has_files") is True:
                queryset = queryset.filter(files__isnull=False).distinct()
            elif filters.get("has_files") is False:
                queryset = queryset.filter(files__isnull=True)

            if filters.get("file_types"):
                queryset = queryset.filter(
                    files__file_type__in=filters["file_types"]
                ).distinct()

            # Order and paginate
            queryset = queryset.order_by("-created_at")

            if cursor:
                queryset = queryset.filter(created_at__lt=cursor)

            posts = list(queryset[: limit + 1])
            has_next = len(posts) > limit

            if has_next:
                posts = posts[:limit]
                next_cursor = posts[-1].created_at.isoformat() if posts else None
            else:
                next_cursor = None

            return posts, has_next, next_cursor

        except Exception as e:
            logger.error(f"Error obteniendo feed filtrado: {str(e)}")
            return [], False, None

    def toggle_comment_like(self, user, comment):
        """
        Alterna like en comentario específico
        """
        try:
            # Toggle like
            like, created = Like.toggle_like(user, comment)

            # Actualizar vectores del usuario si se creó el like
            if created:
                user_vector_service.update_user_vectors_on_interaction(
                    user_id=user.id,
                    interaction_type="like",
                    content=comment.content[:100],
                )

            logger.info(
                f"Like {'creado' if created else 'eliminado'}: Usuario {user.id} - "
                f"Comentario {comment.id}"
            )
            return created  # Return True if liked, False if unliked

        except Exception as e:
            logger.error(f"Error toggleando like en comentario: {str(e)}")
            return False

    def search_posts_by_similarity(
        self, query: str, limit: int = 20, similarity_threshold: float = 0.4
    ) -> list[FeedPost]:
        """
        Búsqueda híbrida: similitud vectorial (dense) + full-text search (sparse).

        Combina embeddings con FTS de PostgreSQL para mejorar relevancia,
        especialmente en corpora homogéneos donde la similitud coseno tiene
        poca varianza. Usa stems truncados para matching cross-idioma
        (e.g., "contin:*" coincide con "continuous" y "continuo").

        Args:
            query: Texto de búsqueda (cualquier idioma)
            limit: Número máximo de resultados
            similarity_threshold: Umbral mínimo de similitud coseno (0-1)

        Returns:
            Lista de posts ordenados por relevancia híbrida
        """
        import math

        try:
            cleaned_query = self._preprocess_search_query(query)
            if not cleaned_query or len(cleaned_query.strip()) < 2:
                logger.warning(f"Query vacío después de limpieza: '{query}'")
                return []

            # ── Paso 1: embedding + texto traducido del microservicio ──
            query_embedding = None
            processed_text = cleaned_query

            try:
                payload = {
                    "text": cleaned_query,
                    "translate_to_english": True,
                    "clean_text": True,
                }
                resp = requests.post(
                    f"{self.embedding_service_url}/text-processing/vectorize/",
                    json=payload,
                    timeout=30,
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code == 200:
                    body = resp.json()
                    query_embedding = body.get("vector")
                    processed_text = body.get("processed_text", cleaned_query)
                    logger.info(
                        f"Búsqueda: '{cleaned_query}' → traducido: '{processed_text}'"
                    )
            except requests.RequestException as e:
                logger.error(f"Error microservicio embeddings: {e}")

            if not query_embedding:
                logger.warning(f"Sin embedding para: {cleaned_query}")
                return list(
                    FeedPost.objects.filter(
                        is_public=True, content__icontains=cleaned_query
                    )
                    .exclude(content__regex=r"^.{0,20}$")
                    .order_by("-created_at")[: min(limit // 3, 5)]
                )

            # ── Paso 2: normalizar embedding (L2) ──
            norm = math.sqrt(sum(x * x for x in query_embedding))
            if norm > 0:
                query_embedding = [x / norm for x in query_embedding]
            embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"

            # ── Paso 3: componentes del score híbrido ──

            # 3a. Similitud coseno vectorial
            similarity_sql = f"(1 - (embedding <=> '{embedding_str}'))"

            # 3b. Full-Text Search con stems prefix (cross-language)
            original_kws = [w for w in cleaned_query.lower().split() if len(w) >= 3]
            english_kws = [w for w in processed_text.lower().split() if len(w) >= 3]

            # Generar stems: primeros 5 chars → matching cross-idioma
            # "continuous" → "conti", "continuo" → "conti" (coinciden!)
            # "deployment" → "deplo", "deploy" → "deplo" (coinciden!)
            import re as _re

            all_stems = set()
            for kw in original_kws + english_kws:
                # Limpiar primero: solo letras y dígitos
                clean_kw = _re.sub(r"[^a-z0-9]", "", kw)
                if len(clean_kw) < 3:
                    continue
                stem = clean_kw[: max(4, min(5, len(clean_kw)))]
                if len(stem) >= 3:
                    all_stems.add(stem)

            if all_stems:
                # tsquery con prefijo: usar formato sin comillas internas
                # to_tsquery('simple', 'conti:* | deplo:* | dock:*')
                tsquery_expr = " | ".join([f"{s}:*" for s in all_stems])
                # Escapar comillas simples en toda la expresión para SQL
                safe_tsquery = tsquery_expr.replace("'", "''")

                # Match booleano: ¿el post contiene al menos un stem?
                fts_match_sql = f"""
                    CASE WHEN
                        to_tsvector('simple', COALESCE("feeds_feedpost"."content", ''))
                        @@ to_tsquery('simple', '{safe_tsquery}')
                    THEN 1.0 ELSE 0.0 END
                """

                # Rank: densidad de coincidencias
                fts_rank_sql = f"""
                    ts_rank_cd(
                        to_tsvector('simple', COALESCE("feeds_feedpost"."content", '')),
                        to_tsquery('simple', '{safe_tsquery}'),
                        32
                    )
                """
            else:
                fts_match_sql = "0"
                fts_rank_sql = "0"

            # 3c. Tag matching (keywords completos + stems en tags)
            all_kw_set = set()
            for kw in original_kws + english_kws:
                clean_kw = _re.sub(r"[^a-z0-9]", "", kw)
                if len(clean_kw) >= 3:
                    all_kw_set.add(clean_kw)
            if all_kw_set:
                tag_parts = []
                for kw in all_kw_set:
                    safe_kw = kw.replace("'", "''").lower()
                    tag_parts.append(
                        f"""CASE WHEN LOWER("feeds_feedpost"."tags"::text) """
                        f"""LIKE '%%{safe_kw}%%' THEN 1 ELSE 0 END"""
                    )
                tag_boost_sql = f"(({' + '.join(tag_parts)})::float / {len(tag_parts)})"
            else:
                tag_boost_sql = "0"

            # ── Paso 4: score híbrido ──
            # 40% vector + 30% FTS match + 10% FTS rank + 10% tags
            # + 7% engagement + 3% recency
            score_sql = f"""
                (
                    {similarity_sql} * 0.40 +
                    {fts_match_sql} * 0.30 +
                    LEAST({fts_rank_sql} * 10.0, 1.0) * 0.10 +
                    {tag_boost_sql} * 0.10 +
                    LEAST(COALESCE("feeds_feedpost"."engagement_score", 0) / 100.0, 1.0) * 0.07 +
                    (1.0 / (1.0 + EXTRACT(EPOCH FROM (NOW() - "feeds_feedpost"."created_at")) / 2592000.0)) * 0.03
                )
            """

            # ── Paso 5: ejecutar query ──
            queryset = (
                FeedPost.objects.filter(
                    is_public=True,
                    embedding__isnull=False,
                    content__isnull=False,
                )
                .exclude(content__exact="")
                .exclude(content__regex=r"^.{0,30}$")
                .annotate(
                    similarity=RawSQL(similarity_sql, []),
                    text_match=RawSQL(fts_match_sql if all_stems else "0", []),
                    text_rank=RawSQL(fts_rank_sql if all_stems else "0", []),
                    relevance_score=RawSQL(score_sql, []),
                )
                .filter(similarity__gte=similarity_threshold)
                .prefetch_related("post_files")
                .order_by("-relevance_score")
            )

            posts = list(queryset[:limit])

            logger.info(
                f"Búsqueda híbrida '{cleaned_query}' (en: '{processed_text}'): "
                f"{len(posts)} resultados (sim >= {similarity_threshold}, "
                f"stems: {all_stems})"
            )

            # Fallback: bajar umbral si no hay resultados
            if (
                not posts
                and similarity_threshold > 0.2
                and len(cleaned_query.split()) >= 2
            ):
                logger.info(
                    f"Sin resultados con umbral {similarity_threshold}, "
                    f"reintentando con 0.2"
                )
                return self.search_posts_by_similarity(
                    query=query,
                    limit=min(limit, 10),
                    similarity_threshold=0.2,
                )

            # Fallback final: búsqueda por texto
            if not posts:
                logger.info(
                    f"Sin resultados vectoriales, fallback a texto: '{cleaned_query}'"
                )
                return list(
                    FeedPost.objects.filter(
                        is_public=True, content__icontains=cleaned_query
                    ).order_by("-created_at")[: limit // 2]
                )

            return posts[:limit]

        except Exception as e:
            logger.error(f"Error en búsqueda híbrida: {str(e)}")
            import traceback

            logger.error(traceback.format_exc())
            cleaned_query = self._preprocess_search_query(query)
            return list(
                FeedPost.objects.filter(
                    is_public=True, content__icontains=cleaned_query
                ).order_by("-created_at")[: limit // 2]
            )

    def _preprocess_search_query(self, query: str) -> str:
        """
        Preprocesa mínimamente el query - el microservicio ya hace el
        filtrado y limpieza
        """
        if not query:
            return ""

        # Solo normalizar espacios múltiples y quitar espacios al inicio/final
        import re

        cleaned = re.sub(r"\s+", " ", query.strip())

        return cleaned


# Instancia global del servicio
feed_service = FeedService()
