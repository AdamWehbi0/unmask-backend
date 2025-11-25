-- Unmask Dating App Database Schema
-- Copy and paste into Supabase SQL Editor

-- Migration 1/27
CREATE TABLE IF NOT EXISTS users (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        name TEXT,
        bio TEXT,
        height_cm INT,
        gender TEXT CHECK (gender IN ('male', 'female', 'non_binary', 'prefer_not_to_say')),
        looking_for TEXT[],
        age INT,
        traits TEXT[],
        values TEXT[],
        green_flags TEXT[],
        red_flags TEXT[],
        lifestyle TEXT[],
        religion TEXT,
        politics TEXT,
        languages TEXT[],
        education TEXT,
        job_title TEXT,
        company TEXT,
        profile_complete BOOLEAN DEFAULT FALSE,
        is_admin BOOLEAN DEFAULT FALSE,
        is_verified BOOLEAN DEFAULT FALSE,
        verification_badge BOOLEAN DEFAULT FALSE,
        deleted_at TIMESTAMP NULL,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );;

-- Migration 2/27
CREATE TABLE IF NOT EXISTS matches (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user1 UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
        user2 UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
        compatibility_score FLOAT DEFAULT 0,
        reveal_user1 BOOLEAN DEFAULT FALSE,
        reveal_user2 BOOLEAN DEFAULT FALSE,
        deleted_at TIMESTAMP NULL,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(user1, user2),
        CHECK (user1 != user2)
    );;

-- Migration 3/27
CREATE TABLE IF NOT EXISTS messages (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        match_id UUID NOT NULL REFERENCES matches(id) ON DELETE RESTRICT,
        sender_id UUID NOT NULL REFERENCES users(id) ON DELETE SET NULL,
        content TEXT NOT NULL,
        is_read BOOLEAN DEFAULT FALSE,
        read_at TIMESTAMP NULL,
        created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_messages_match_id ON messages(match_id);
    CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(match_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_messages_is_read ON messages(match_id, is_read) WHERE is_read = FALSE;;

-- Migration 4/27
CREATE TABLE IF NOT EXISTS user_locations (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
        latitude DECIMAL(10, 8) NOT NULL,
        longitude DECIMAL(11, 8) NOT NULL,
        accuracy_meters INT,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_user_locations_coordinates ON user_locations(latitude, longitude);;

-- Migration 5/27
CREATE TABLE IF NOT EXISTS user_verifications (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
        storage_path TEXT,
        id_type TEXT CHECK (id_type IN ('passport', 'driver_license', 'national_id')),
        status TEXT CHECK (status IN ('pending', 'approved', 'rejected')) DEFAULT 'pending',
        verified_at TIMESTAMP NULL,
        expires_at TIMESTAMP NULL,
        rejection_reason TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_user_verifications_user_id ON user_verifications(user_id);
    CREATE INDEX IF NOT EXISTS idx_user_verifications_status ON user_verifications(status);;

-- Migration 6/27
CREATE TABLE IF NOT EXISTS user_blocks (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        blocker_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        blocked_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        deleted_at TIMESTAMP NULL,
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(blocker_id, blocked_id),
        CHECK (blocker_id != blocked_id)
    );
    CREATE INDEX IF NOT EXISTS idx_user_blocks_blocker ON user_blocks(blocker_id) WHERE deleted_at IS NULL;
    CREATE INDEX IF NOT EXISTS idx_user_blocks_blocked ON user_blocks(blocked_id) WHERE deleted_at IS NULL;;

-- Migration 7/27
CREATE TABLE IF NOT EXISTS abuse_reports (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        reporter_id UUID NOT NULL REFERENCES users(id) ON DELETE SET NULL,
        reported_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        reason TEXT CHECK (reason IN ('inappropriate_profile', 'harassing_messages', 'bot_account', 'catfish', 'explicit_content', 'scam', 'other')) NOT NULL,
        details TEXT,
        status TEXT CHECK (status IN ('pending', 'resolved', 'dismissed')) DEFAULT 'pending',
        reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
        resolution_notes TEXT,
        deleted_at TIMESTAMP NULL,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_abuse_reports_status ON abuse_reports(status) WHERE deleted_at IS NULL;
    CREATE INDEX IF NOT EXISTS idx_abuse_reports_reported ON abuse_reports(reported_id) WHERE deleted_at IS NULL;
    CREATE INDEX IF NOT EXISTS idx_abuse_reports_created ON abuse_reports(created_at DESC) WHERE deleted_at IS NULL;;

-- Migration 8/27
CREATE TABLE IF NOT EXISTS user_actions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        action_type TEXT CHECK (action_type IN ('like', 'pass', 'undo')) NOT NULL,
        target_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        match_id UUID REFERENCES matches(id) ON DELETE SET NULL,
        status TEXT CHECK (status IN ('pending', 'completed', 'failed')) DEFAULT 'completed',
        deleted_at TIMESTAMP NULL,
        created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_user_actions_user ON user_actions(user_id, created_at DESC) WHERE deleted_at IS NULL;
    CREATE INDEX IF NOT EXISTS idx_user_actions_target ON user_actions(target_user_id) WHERE deleted_at IS NULL;
    CREATE INDEX IF NOT EXISTS idx_user_actions_type ON user_actions(user_id, action_type, created_at DESC) WHERE deleted_at IS NULL;;

-- Migration 9/27
CREATE TABLE IF NOT EXISTS user_subscriptions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
        plan TEXT CHECK (plan IN ('free', 'premium', 'vip')) DEFAULT 'free',
        stripe_customer_id TEXT,
        stripe_subscription_id TEXT,
        super_likes_remaining INT DEFAULT 0,
        boosts_remaining INT DEFAULT 0,
        rewinds_remaining INT DEFAULT 0,
        boost_expires_at TIMESTAMP NULL,
        expires_at TIMESTAMP NULL,
        deleted_at TIMESTAMP NULL,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_user_subscriptions_plan ON user_subscriptions(plan);
    CREATE INDEX IF NOT EXISTS idx_user_subscriptions_expires ON user_subscriptions(expires_at) WHERE expires_at IS NOT NULL;;

-- Migration 10/27
CREATE TABLE IF NOT EXISTS analytics_events (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID REFERENCES users(id) ON DELETE SET NULL,
        event_type TEXT NOT NULL,
        event_data JSONB,
        created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_analytics_events_user ON analytics_events(user_id);
    CREATE INDEX IF NOT EXISTS idx_analytics_events_type ON analytics_events(event_type);
    CREATE INDEX IF NOT EXISTS idx_analytics_events_created ON analytics_events(created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_analytics_events_user_type ON analytics_events(user_id, event_type, created_at DESC);;

-- Migration 11/27
CREATE TABLE IF NOT EXISTS notification_tokens (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        device_token TEXT NOT NULL,
        platform TEXT CHECK (platform IN ('ios', 'android')) NOT NULL,
        deleted_at TIMESTAMP NULL,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    CREATE UNIQUE INDEX IF NOT EXISTS idx_notification_tokens_device ON notification_tokens(user_id, device_token) WHERE deleted_at IS NULL;
    CREATE INDEX IF NOT EXISTS idx_notification_tokens_user ON notification_tokens(user_id) WHERE deleted_at IS NULL;;

-- Migration 12/27
CREATE TABLE IF NOT EXISTS notifications_sent (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        recipient_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        notification_type TEXT NOT NULL,
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        data JSONB,
        is_sent BOOLEAN DEFAULT FALSE,
        sent_at TIMESTAMP NULL,
        created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_notifications_sent_recipient ON notifications_sent(recipient_id);
    CREATE INDEX IF NOT EXISTS idx_notifications_sent_status ON notifications_sent(is_sent, created_at DESC);;

-- Migration 13/27
CREATE TABLE IF NOT EXISTS audit_logs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        admin_id UUID NOT NULL REFERENCES users(id) ON DELETE SET NULL,
        action TEXT NOT NULL,
        target_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
        details JSONB,
        created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_audit_logs_admin ON audit_logs(admin_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_audit_logs_target ON audit_logs(target_user_id, created_at DESC);;

-- Migration 14/27
CREATE TABLE IF NOT EXISTS interest_categories (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name TEXT UNIQUE NOT NULL,
        category TEXT NOT NULL,
        emoji TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_interest_categories_name ON interest_categories(name);
    CREATE INDEX IF NOT EXISTS idx_interest_categories_category ON interest_categories(category);;

-- Migration 15/27
CREATE TABLE IF NOT EXISTS user_interests (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        interest_id UUID NOT NULL REFERENCES interest_categories(id) ON DELETE CASCADE,
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(user_id, interest_id)
    );
    CREATE INDEX IF NOT EXISTS idx_user_interests_user ON user_interests(user_id);
    CREATE INDEX IF NOT EXISTS idx_user_interests_interest ON user_interests(interest_id);;

-- Migration 16/27
CREATE TABLE IF NOT EXISTS user_pets (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
        has_dogs BOOLEAN DEFAULT FALSE,
        has_cats BOOLEAN DEFAULT FALSE,
        has_other_pets BOOLEAN DEFAULT FALSE,
        other_pets_description TEXT,
        likes_dogs BOOLEAN DEFAULT TRUE,
        likes_cats BOOLEAN DEFAULT TRUE,
        wants_pet BOOLEAN DEFAULT FALSE,
        pet_allergies TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_user_pets_user ON user_pets(user_id);;

-- Migration 17/27
CREATE TABLE IF NOT EXISTS user_lifestyle (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
        smoking TEXT CHECK (smoking IN ('no', 'socially', 'regularly')),
        drinking TEXT CHECK (drinking IN ('no', 'socially', 'regularly')),
        drugs TEXT CHECK (drugs IN ('no', 'socially', 'regularly')),
        sleep_schedule TEXT CHECK (sleep_schedule IN ('early_bird', 'night_owl', 'varies')),
        diet TEXT CHECK (diet IN ('omnivore', 'vegetarian', 'vegan', 'pescatarian')),
        exercise_frequency TEXT CHECK (exercise_frequency IN ('daily', '3-5x_week', '1-2x_week', 'rarely', 'never')),
        social_lifestyle TEXT CHECK (social_lifestyle IN ('introverted', 'ambivert', 'extroverted')),
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_user_lifestyle_user ON user_lifestyle(user_id);;

-- Migration 18/27
CREATE TABLE IF NOT EXISTS user_goals (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
        wants_kids TEXT CHECK (wants_kids IN ('yes', 'no', 'maybe', 'already_have')),
        marriage_timeline TEXT CHECK (marriage_timeline IN ('not_sure', 'not_interested', '1-2_years', '3-5_years', '5+_years')),
        relationship_type TEXT CHECK (relationship_type IN ('casual', 'dating', 'serious', 'long_term', 'open')),
        career_ambition TEXT CHECK (career_ambition IN ('climbing_ladder', 'stable_job', 'work_life_balance', 'pursuing_passion')),
        travel_frequency TEXT CHECK (travel_frequency IN ('rarely', 'once_year', 'multiple_times', 'constantly')),
        financial_goals TEXT CHECK (financial_goals IN ('saving', 'investing', 'enjoying_life', 'building_wealth')),
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_user_goals_user ON user_goals(user_id);;

-- Migration 19/27
CREATE TABLE IF NOT EXISTS user_badges (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        badge_type TEXT NOT NULL,
        earned_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(user_id, badge_type)
    );
    CREATE INDEX IF NOT EXISTS idx_user_badges_user ON user_badges(user_id);
    CREATE INDEX IF NOT EXISTS idx_user_badges_type ON user_badges(badge_type);;

-- Migration 20/27
CREATE TABLE IF NOT EXISTS user_filters (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
        min_age INT DEFAULT 18,
        max_age INT DEFAULT 50,
        max_distance_km INT DEFAULT 30,
        relationship_types TEXT[],
        preferred_interests TEXT[],
        preferred_goals TEXT[],
        show_only_verified BOOLEAN DEFAULT FALSE,
        show_only_with_photo BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_user_filters_user ON user_filters(user_id);;

-- Migration 21/27
CREATE TABLE IF NOT EXISTS photo_uploads (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        storage_path TEXT NOT NULL,
        thumbnail_url TEXT,
        medium_url TEXT,
        full_url TEXT,
        photo_order INT DEFAULT 0,
        is_primary BOOLEAN DEFAULT FALSE,
        deleted_at TIMESTAMP NULL,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_photo_uploads_user ON photo_uploads(user_id) WHERE deleted_at IS NULL;
    CREATE INDEX IF NOT EXISTS idx_photo_uploads_order ON photo_uploads(user_id, photo_order) WHERE deleted_at IS NULL;;

-- Migration 22/27
CREATE TABLE IF NOT EXISTS fraud_flags (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        flag_type TEXT NOT NULL,
        severity TEXT CHECK (severity IN ('low', 'medium', 'high')) DEFAULT 'low',
        details JSONB,
        resolved_at TIMESTAMP NULL,
        resolved_by UUID REFERENCES users(id) ON DELETE SET NULL,
        resolution_notes TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_fraud_flags_user ON fraud_flags(user_id);
    CREATE INDEX IF NOT EXISTS idx_fraud_flags_severity ON fraud_flags(severity) WHERE resolved_at IS NULL;
    CREATE INDEX IF NOT EXISTS idx_fraud_flags_created ON fraud_flags(created_at DESC) WHERE resolved_at IS NULL;;

-- Migration 23/27
CREATE TABLE IF NOT EXISTS trust_scores (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
        overall_score FLOAT DEFAULT 0.5,
        account_age_score FLOAT DEFAULT 0.5,
        photo_verification_score FLOAT DEFAULT 0.5,
        message_quality_score FLOAT DEFAULT 0.5,
        report_count INT DEFAULT 0,
        behavior_score FLOAT DEFAULT 0.5,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_trust_scores_user ON trust_scores(user_id);
    CREATE INDEX IF NOT EXISTS idx_trust_scores_overall ON trust_scores(overall_score DESC);;

-- Migration 24/27
CREATE TABLE IF NOT EXISTS account_status (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
        is_deactivated BOOLEAN DEFAULT FALSE,
        deactivation_start TIMESTAMP NULL,
        deactivation_end TIMESTAMP NULL,
        deletion_requested_at TIMESTAMP NULL,
        deletion_scheduled_for TIMESTAMP NULL,
        deletion_reason TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_account_status_user ON account_status(user_id);
    CREATE INDEX IF NOT EXISTS idx_account_status_deletion ON account_status(deletion_scheduled_for) WHERE deletion_scheduled_for IS NOT NULL;;

-- Migration 25/27
CREATE TABLE IF NOT EXISTS data_exports (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        export_format TEXT CHECK (export_format IN ('json', 'csv')) DEFAULT 'json',
        storage_path TEXT NOT NULL,
        file_size_bytes INT,
        expires_at TIMESTAMP NOT NULL,
        downloaded_at TIMESTAMP NULL,
        created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_data_exports_user ON data_exports(user_id);
    CREATE INDEX IF NOT EXISTS idx_data_exports_expires ON data_exports(expires_at);;

-- Migration 26/27
CREATE TABLE IF NOT EXISTS deletion_audit_log (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL,
        admin_id UUID REFERENCES users(id) ON DELETE SET NULL,
        field_name TEXT NOT NULL,
        old_value_hash TEXT,
        reason TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_deletion_audit_user ON deletion_audit_log(user_id);
    CREATE INDEX IF NOT EXISTS idx_deletion_audit_admin ON deletion_audit_log(admin_id);
    CREATE INDEX IF NOT EXISTS idx_deletion_audit_created ON deletion_audit_log(created_at DESC);;

-- Migration 27/27
CREATE TABLE IF NOT EXISTS user_rewinds (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        rewound_action_id UUID NOT NULL REFERENCES user_actions(id) ON DELETE CASCADE,
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(rewound_action_id)
    );
    CREATE INDEX IF NOT EXISTS idx_user_rewinds_user ON user_rewinds(user_id);
    CREATE INDEX IF NOT EXISTS idx_user_rewinds_created ON user_rewinds(created_at DESC);;

