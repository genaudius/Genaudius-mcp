-- ═══════════════════════════════════════════════════════════════════
-- MusicGAU By Gen Audius - Supabase Schema Setup (Cluster Version)
-- ═══════════════════════════════════════════════════════════════════

-- 1. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Knowledge Base: PDFs, Manuals, Theory
CREATE TABLE IF NOT EXISTS knowledge_base (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    embedding VECTOR(1536), -- text-embedding-3-small
    metadata JSONB, -- { "type": "theory", "source": "manual_mezcla.pdf" }
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. MIDI Library: ABC Notation Patterns with Cluster Tagging
CREATE TABLE IF NOT EXISTS midi_library (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    abc_notation TEXT NOT NULL,
    embedding VECTOR(1536),
    group_id TEXT,    -- 'percussion', 'harmony', 'vocals'
    style_tag TEXT,   -- 'tradicional', 'moderno', 'sinfonico'
    role_id TEXT,     -- 'bajo', 'guira', 'violin_1', 'whisper_vocals'
    metadata JSONB,   -- any additional info
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_midi_group ON midi_library (group_id);
CREATE INDEX IF NOT EXISTS idx_midi_style ON midi_library (style_tag);

-- 4. Role Definitions: Musician "Profiles"
CREATE TABLE IF NOT EXISTS role_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument_role TEXT UNIQUE NOT NULL, -- 'bass', 'requinto', 'whisper_vocals'
    group_id TEXT NOT NULL,               -- 'percussion', 'harmony', 'vocals'
    style_guidelines TEXT,
    system_prompt_addition TEXT,
    metadata JSONB
);

-- 5. Instrument Orchestration: Genre to Cluster Mapping
CREATE TABLE IF NOT EXISTS instrument_orchestration (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    genre TEXT UNIQUE NOT NULL, -- 'bachata_tradicional', 'bachata_moderna', 'symphonic'
    clusters JSONB, -- { "percussion": [...], "harmony": [...], "vocals": [...] }
    metadata JSONB
);

-- 6. Recording Sessions: Temporary parts for reassembly
CREATE TABLE IF NOT EXISTS recording_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    cluster_id TEXT NOT NULL,
    instrument_role TEXT NOT NULL,
    part_abc TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════════
-- Vector Search Functions (Optimized for Clusters)
-- ═══════════════════════════════════════════════════════════════════

-- Match MIDI Patterns with Cluster Filtering
CREATE OR REPLACE FUNCTION match_midi_patterns (
  query_embedding VECTOR(1536),
  filter_group TEXT,
  filter_style TEXT,
  filter_role TEXT,
  match_threshold FLOAT,
  match_count INT
)
RETURNS TABLE (
  id UUID,
  abc_notation TEXT,
  group_id TEXT,
  style_tag TEXT,
  role_id TEXT,
  similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    midi_library.id,
    midi_library.abc_notation,
    midi_library.group_id,
    midi_library.style_tag,
    midi_library.role_id,
    1 - (midi_library.embedding <=> query_embedding) AS similarity
  FROM midi_library
  WHERE 
    (filter_group IS NULL OR midi_library.group_id = filter_group)
    AND (filter_style IS NULL OR midi_library.style_tag = filter_style)
    AND (filter_role IS NULL OR midi_library.role_id = filter_role)
    AND 1 - (midi_library.embedding <=> query_embedding) > match_threshold
  ORDER BY similarity DESC
  LIMIT match_count;
END;
$$;

-- ═══════════════════════════════════════════════════════════════════
-- Seed Data: Clusters Orchestration
-- ═══════════════════════════════════════════════════════════════════

INSERT INTO instrument_orchestration (genre, clusters) VALUES
('bachata_tradicional', '{
    "percussion": ["bongo", "guira"],
    "harmony": ["bass", "requinto", "segunda"],
    "vocals": ["voz_lider", "coros", "duos"]
}'),
('bachata_moderna', '{
    "percussion": ["bongo", "guira", "conga", "timbal", "kit", "campana"],
    "harmony": ["bass", "requinto", "segunda", "piano", "pads", "strings", "violin", "cello"],
    "vocals": ["voz_lider", "coros", "duo", "voz_fem", "voz_masc", "whisper_vocals"]
}'),
('symphonic', '{
    "percussion": ["timpani", "percussion_orch"],
    "harmony": ["violin_1", "violin_2", "viola", "cello", "contrabasso", "flute", "oboe", "clarinet", "bassoon", "horn", "trumpet", "trombone", "tuba"],
    "vocals": ["soprano", "alto", "tenor", "bass_choir"]
}')
ON CONFLICT (genre) DO UPDATE SET clusters = EXCLUDED.clusters;
