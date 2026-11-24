CREATE TABLE `bot_sessions` (
	`telegram_user_id` text PRIMARY KEY NOT NULL,
	`step` text NOT NULL,
	`category` text,
	`amount_kopecks` integer,
	`updated_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL
);
--> statement-breakpoint
CREATE TABLE `expenses` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`expense_date` text NOT NULL,
	`category` text NOT NULL,
	`amount_kopecks` integer NOT NULL,
	`comment` text DEFAULT '' NOT NULL,
	`source` text DEFAULT 'CRM' NOT NULL,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	`updated_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL
);
--> statement-breakpoint
CREATE INDEX `idx_expenses_date_category` ON `expenses` (`expense_date`,`category`);