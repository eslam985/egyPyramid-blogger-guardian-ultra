import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = "https://syprdvmgktmlrbdqwjif.supabase.co";
const SUPABASE_KEY = "sb_publishable_W09k2FI0QhaRv5UQKmoabA_Z_rmAkQ3";

export const supabaseClient = createClient(SUPABASE_URL, SUPABASE_KEY);