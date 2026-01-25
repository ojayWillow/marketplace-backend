-- Add attachment fields to messages table
-- Run this migration to enable file/image attachments in chat

ALTER TABLE messages ADD COLUMN attachment_url VARCHAR(500);
ALTER TABLE messages ADD COLUMN attachment_type VARCHAR(20);

-- Verify columns were added
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'messages' 
AND column_name IN ('attachment_url', 'attachment_type');
