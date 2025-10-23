-- public.pages definição
-- Drop table
-- DROP TABLE public.pages;

CREATE TABLE public.pages (
	id text NOT NULL,
	url text NOT NULL,
	is_active bool DEFAULT true NULL,
	last_crawled_at timestamptz DEFAULT now() NULL,
	CONSTRAINT pages_pkey PRIMARY KEY (id)
);

-- Permissions

ALTER TABLE public.pages OWNER TO scraper;
GRANT ALL ON TABLE public.pages TO scraper;


-- public.scrape_history definição
-- Drop table
-- DROP TABLE public.scrape_history;

CREATE TABLE public.scrape_history (
	id serial4 NOT NULL,
	page_id text NULL,
	scrape_timestamp timestamptz NOT NULL,
	modified_date text NULL,
	updated_by text NULL,
	responsible text NULL,
	full_modified_text text NULL,
	CONSTRAINT scrape_history_pkey PRIMARY KEY (id),
	CONSTRAINT scrape_history_page_id_fkey FOREIGN KEY (page_id) REFERENCES public.pages(id)
);
CREATE INDEX idx_history_scrape_timestamp ON public.scrape_history USING btree (scrape_timestamp);

-- Permissions

ALTER TABLE public.scrape_history OWNER TO scraper;
GRANT ALL ON TABLE public.scrape_history TO scraper;