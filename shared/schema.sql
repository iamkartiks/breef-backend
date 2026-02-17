-- Research Paper Platform Database Schema
-- This schema extends Supabase's built-in auth.users table

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Papers table (arXiv metadata cache)
CREATE TABLE IF NOT EXISTS papers (
    arxiv_id VARCHAR(50) PRIMARY KEY,
    title TEXT NOT NULL,
    abstract TEXT NOT NULL,
    authors JSONB NOT NULL, -- Array of {name, affiliation}
    categories JSONB NOT NULL, -- {primary: string, secondary: string[]}
    published TIMESTAMPTZ NOT NULL,
    updated TIMESTAMPTZ NOT NULL,
    pdf_url TEXT NOT NULL,
    arxiv_url TEXT NOT NULL,
    doi VARCHAR(255),
    journal_ref TEXT,
    primary_category VARCHAR(50) NOT NULL,
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    -- Indexes for common queries
    CONSTRAINT papers_arxiv_id_check CHECK (arxiv_id ~ '^[0-9]{4}\.[0-9]{4,5}(v[0-9]+)?$')
);

-- Indexes for papers
CREATE INDEX IF NOT EXISTS idx_papers_published ON papers(published DESC);
CREATE INDEX IF NOT EXISTS idx_papers_primary_category ON papers(primary_category);
CREATE INDEX IF NOT EXISTS idx_papers_updated ON papers(updated DESC);
CREATE INDEX IF NOT EXISTS idx_papers_title_search ON papers USING gin(to_tsvector('english', title));
CREATE INDEX IF NOT EXISTS idx_papers_abstract_search ON papers USING gin(to_tsvector('english', abstract));

-- User profiles (extends auth.users)
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    bio TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- User paper interactions (bookmarks, reading history)
CREATE TABLE IF NOT EXISTS user_papers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    paper_id VARCHAR(50) NOT NULL REFERENCES papers(arxiv_id) ON DELETE CASCADE,
    bookmarked BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMPTZ,
    last_viewed TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, paper_id)
);

-- Indexes for user_papers
CREATE INDEX IF NOT EXISTS idx_user_papers_user_id ON user_papers(user_id);
CREATE INDEX IF NOT EXISTS idx_user_papers_paper_id ON user_papers(paper_id);
CREATE INDEX IF NOT EXISTS idx_user_papers_bookmarked ON user_papers(user_id, bookmarked) WHERE bookmarked = TRUE;
CREATE INDEX IF NOT EXISTS idx_user_papers_last_viewed ON user_papers(user_id, last_viewed DESC);

-- AI conversations
CREATE TABLE IF NOT EXISTS ai_conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    paper_id VARCHAR(50) NOT NULL REFERENCES papers(arxiv_id) ON DELETE CASCADE,
    messages JSONB NOT NULL DEFAULT '[]'::jsonb, -- Array of {role, content, timestamp}
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for ai_conversations
CREATE INDEX IF NOT EXISTS idx_ai_conversations_user_id ON ai_conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_ai_conversations_paper_id ON ai_conversations(paper_id);
CREATE INDEX IF NOT EXISTS idx_ai_conversations_user_paper ON ai_conversations(user_id, paper_id);

-- Subscriptions (to authors, categories, keywords)
CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    type VARCHAR(20) NOT NULL CHECK (type IN ('author', 'category', 'keyword')),
    target TEXT NOT NULL, -- author name, category, or keyword
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, type, target)
);

-- Indexes for subscriptions
CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_type_target ON subscriptions(type, target);

-- Paper votes (upvotes and downvotes)
CREATE TABLE IF NOT EXISTS paper_votes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    paper_id VARCHAR(50) NOT NULL REFERENCES papers(arxiv_id) ON DELETE CASCADE,
    vote_type VARCHAR(10) NOT NULL CHECK (vote_type IN ('upvote', 'downvote')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, paper_id)
);

-- Indexes for paper_votes
CREATE INDEX IF NOT EXISTS idx_paper_votes_user_id ON paper_votes(user_id);
CREATE INDEX IF NOT EXISTS idx_paper_votes_paper_id ON paper_votes(paper_id);
CREATE INDEX IF NOT EXISTS idx_paper_votes_paper_type ON paper_votes(paper_id, vote_type);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers to auto-update updated_at
CREATE TRIGGER update_papers_updated_at BEFORE UPDATE ON papers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_profiles_updated_at BEFORE UPDATE ON user_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_papers_updated_at BEFORE UPDATE ON user_papers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_ai_conversations_updated_at BEFORE UPDATE ON ai_conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to handle new user signup
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.user_profiles (id, email, full_name)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', NULL)
    )
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to create user profile on signup
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- Row Level Security (RLS) Policies
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_papers ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

-- User profiles policies
CREATE POLICY "Users can view own profile" ON user_profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON user_profiles
    FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Users can insert own profile" ON user_profiles
    FOR INSERT WITH CHECK (auth.uid() = id);

-- User papers policies
CREATE POLICY "Users can view own paper interactions" ON user_papers
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can manage own paper interactions" ON user_papers
    FOR ALL USING (auth.uid() = user_id);

-- AI conversations policies
CREATE POLICY "Users can view own conversations" ON ai_conversations
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can manage own conversations" ON ai_conversations
    FOR ALL USING (auth.uid() = user_id);

-- Subscriptions policies
CREATE POLICY "Users can view own subscriptions" ON subscriptions
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can manage own subscriptions" ON subscriptions
    FOR ALL USING (auth.uid() = user_id);

-- Paper votes policies
ALTER TABLE paper_votes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can view votes" ON paper_votes
    FOR SELECT USING (true);

CREATE POLICY "Users can manage own votes" ON paper_votes
    FOR ALL USING (auth.uid() = user_id);

