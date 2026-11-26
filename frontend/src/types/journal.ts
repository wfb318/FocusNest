export interface JournalSummary {
  id: string
  entry_date: string
  title: string
  revision: string
  created_at: string
  updated_at: string
}
export interface Journal extends JournalSummary { content: string }
export interface JournalDay { entry_date: string; entry: Journal | null }
export interface JournalPage { items: JournalSummary[]; total: number; page: number; page_size: number }
export interface JournalInput { title: string; content: string; expected_revision: string | null }
export interface JournalQuery { page: number; page_size: number; start_date?: string; end_date?: string; q?: string }
