// ╔══════════════════════════════════════════════════════════════╗
// ║  User Profile & Settings Page                               ║
// ║                                                             ║
// ║  Features:                                                  ║
// ║  • Gmail/Outlook credentials management                     ║
// ║  • Custom email filters (include/exclude)                   ║
// ║  • Region selection with default filters                    ║
// ║  • Telegram notifications config                            ║
// ╚══════════════════════════════════════════════════════════════╝

"use client";

import { useState, useEffect } from "react";
import { createClient } from "@/lib/supabase/client";
import { PlusIcon, TrashIcon } from "@heroicons/react/24/outline";
import styles from "./profile.module.css";

interface EmailFilter {
  id: string;
  filter_type: 'include' | 'exclude';
  field: 'subject' | 'sender' | 'body';
  pattern: string;
  is_regex: boolean;
  is_active: boolean;
  priority: number;
}

interface UserProfile {
  id: string;
  email: string;
  full_name: string | null;
  region: 'en' | 'de' | 'fr' | 'es';
  gmail_credentials: any;
  telegram_enabled: boolean;
  telegram_bot_token: string | null;
  telegram_chat_id: string | null;
}

export default function ProfileSettingsPage() {
  const supabase = createClient();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [filters, setFilters] = useState<EmailFilter[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  // ══════════════════════════════════════════════════════════════
  // Load user profile and filters
  // ══════════════════════════════════════════════════════════════

  useEffect(() => {
    loadProfile();
    loadFilters();
  }, []);

  async function loadProfile() {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      let { data, error } = await supabase
        .from('user_profiles')
        .select('*')
        .eq('id', user.id)
        .single();

      // Auto-create profile if it doesn't exist (fallback for missing trigger)
      if (!data || error?.code === 'PGRST116') {
        const { data: newProfile, error: upsertError } = await supabase
          .from('user_profiles')
          .upsert({ id: user.id, email: user.email! })
          .select()
          .single();

        if (upsertError) throw upsertError;

        // Initialize default filters for the new profile
        await supabase.rpc('initialize_user', {
          p_user_id: user.id,
          p_region: 'en'
        });

        data = newProfile;
        error = null;
      }

      if (error) throw error;
      setProfile(data);
    } catch (error: any) {
      console.error('Failed to load profile:', error);
    } finally {
      setLoading(false);
    }
  }

  async function loadFilters() {
    try {
      const { data, error } = await supabase
        .from('email_filters')
        .select('*')
        .order('priority', { ascending: true });

      if (error) throw error;
      setFilters(data || []);
    } catch (error: any) {
      console.error('Failed to load filters:', error);
    }
  }

  // ══════════════════════════════════════════════════════════════
  // Save profile
  // ══════════════════════════════════════════════════════════════

  async function saveProfile(updates: Partial<UserProfile>) {
    setSaving(true);
    setMessage("");

    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) throw new Error("Not authenticated");

      const { error } = await supabase
        .from('user_profiles')
        .update(updates)
        .eq('id', user.id);

      if (error) throw error;

      setProfile(prev => prev ? { ...prev, ...updates } : null);
      setMessage("Profile updated successfully!");
    } catch (error: any) {
      setMessage(`Failed to save: ${error.message}`);
    } finally {
      setSaving(false);
    }
  }

  // ══════════════════════════════════════════════════════════════
  // Region change handler (resets filters to region defaults)
  // ══════════════════════════════════════════════════════════════

  async function changeRegion(newRegion: string) {
    if (!confirm(
      "Changing region will reset your email filters to defaults. Continue?"
    )) return;

    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) throw new Error("Not authenticated");

      // Call database function to reinitialize user with new region
      const { error } = await supabase.rpc('initialize_user', {
        p_user_id: user.id,
        p_region: newRegion
      });

      if (error) throw error;

      setProfile(prev => prev ? { ...prev, region: newRegion as any } : null);
      loadFilters(); // Reload filters
      setMessage(`Region changed to ${newRegion.toUpperCase()}. Default filters applied.`);
    } catch (error: any) {
      setMessage(`Failed to change region: ${error.message}`);
    }
  }

  // ══════════════════════════════════════════════════════════════
  // Filter management
  // ══════════════════════════════════════════════════════════════

  async function addFilter() {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) throw new Error("Not authenticated");

      const { data, error } = await supabase
        .from('email_filters')
        .insert({
          user_id: user.id,
          filter_type: 'include',
          field: 'subject',
          pattern: '',
          is_regex: false,
          is_active: true,
          priority: filters.length
        })
        .select()
        .single();

      if (error) throw error;
      setFilters([...filters, data]);
    } catch (error: any) {
      setMessage(`Failed to add filter: ${error.message}`);
    }
  }

  async function updateFilter(filterId: string, updates: Partial<EmailFilter>) {
    try {
      const { error } = await supabase
        .from('email_filters')
        .update(updates)
        .eq('id', filterId);

      if (error) throw error;

      setFilters(filters.map(f => 
        f.id === filterId ? { ...f, ...updates } : f
      ));
    } catch (error: any) {
      setMessage(`Failed to update filter: ${error.message}`);
    }
  }

  async function deleteFilter(filterId: string) {
    try {
      const { error } = await supabase
        .from('email_filters')
        .delete()
        .eq('id', filterId);

      if (error) throw error;
      setFilters(filters.filter(f => f.id !== filterId));
    } catch (error: any) {
      setMessage(`Failed to delete filter: ${error.message}`);
    }
  }

  // ══════════════════════════════════════════════════════════════
  // Gmail OAuth flow (placeholder - needs Google OAuth setup)
  // ══════════════════════════════════════════════════════════════

  function connectGmail() {
    // TODO: Implement Google OAuth flow
    // 1. Redirect to Google OAuth consent screen
    // 2. Get authorization code
    // 3. Exchange for tokens
    // 4. Store encrypted tokens in user_profiles.gmail_credentials
    
    alert("Gmail OAuth integration - Coming soon!\n\nYou'll be able to:\n1. Authorize BewerbLens to access Gmail\n2. Store encrypted credentials securely\n3. Auto-sync emails on schedule");
  }

  // ══════════════════════════════════════════════════════════════
  // Render
  // ══════════════════════════════════════════════════════════════

  if (loading) {
    return <div className={styles.loading}>Loading profile...</div>;
  }

  if (!profile) {
    return (
      <div className={styles.error}>
        <p>Could not load your profile. Please sign in and try again.</p>
        <a href="/login" className={styles.loginLink}>Go to Login</a>
      </div>
    );
  }

  return (
    <div className={styles.profileContainer}>
      <h1>Profile & Settings</h1>

      {message && <div className={styles.message}>{message}</div>}

      {/* ═══ SECTION 1: Basic Info ═══ */}
      <section className={styles.section}>
        <h2>Basic Information</h2>
        
        <div className={styles.formGroup}>
          <label>Email</label>
          <input type="text" value={profile.email} disabled />
        </div>

        <div className={styles.formGroup}>
          <label>Full Name</label>
          <input
            type="text"
            value={profile.full_name || ''}
            onChange={(e) => setProfile({ ...profile, full_name: e.target.value })}
            onBlur={() => saveProfile({ full_name: profile.full_name })}
          />
        </div>

        <div className={styles.formGroup}>
          <label>Region / Language</label>
          <select
            value={profile.region}
            onChange={(e) => changeRegion(e.target.value)}
          >
            <option value="en">English (EN)</option>
            <option value="de">German (DE)</option>
            <option value="fr">French (FR)</option>
            <option value="es">Spanish (ES)</option>
          </select>
          <p className={styles.helpText}>
            Changes region-specific email filters (keywords for application emails)
          </p>
        </div>
      </section>

      {/* ═══ SECTION 2: Email Providers ═══ */}
      <section className={styles.section}>
        <h2>Email Providers</h2>
        
        <div className={styles.providerCard}>
          <div className={styles.providerHeader}>
            <h3>Gmail</h3>
            <span className={profile.gmail_credentials ? styles.statusConnected : styles.statusDisconnected}>
              {profile.gmail_credentials ? "Connected" : "Not connected"}
            </span>
          </div>
          <p>Connect your Gmail account to automatically track job application emails.</p>
          <button onClick={connectGmail} className={styles.btnPrimary}>
            {profile.gmail_credentials ? "Reconnect Gmail" : "Connect Gmail"}
          </button>
        </div>

        <div className={`${styles.providerCard} ${styles.disabled}`}>
          <div className={styles.providerHeader}>
            <h3>Outlook</h3>
            <span className="badge">Coming Soon</span>
          </div>
          <p>Microsoft Outlook integration will be available in a future update.</p>
        </div>
      </section>

      {/* ═══ SECTION 3: Email Filters ═══ */}
      <section className={styles.section}>
        <h2>Email Filters</h2>
        <p className={styles.helpText}>
          Define rules to automatically include or exclude emails from tracking.
          Default filters are applied based on your region.
        </p>

        <button onClick={addFilter} className={styles.btnSecondary}>
          <PlusIcon className={styles.icon} /> Add Filter
        </button>

        <div className={styles.filtersList}>
          {filters.map((filter) => (
            <div key={filter.id} className={styles.filterCard}>
              <div className={styles.filterRow}>
                <select
                  value={filter.filter_type}
                  onChange={(e) => updateFilter(filter.id, { 
                    filter_type: e.target.value as 'include' | 'exclude' 
                  })}
                  className={styles.filterType}
                >
                  <option value="include">Include</option>
                  <option value="exclude">Exclude</option>
                </select>

                <span className={styles.filterText}>emails where</span>

                <select
                  value={filter.field}
                  onChange={(e) => updateFilter(filter.id, { 
                    field: e.target.value as 'subject' | 'sender' | 'body'
                  })}
                >
                  <option value="subject">Subject</option>
                  <option value="sender">Sender</option>
                  <option value="body">Body</option>
                </select>

                <span className={styles.filterText}>contains</span>

                <input
                  type="text"
                  value={filter.pattern}
                  onChange={(e) => updateFilter(filter.id, { pattern: e.target.value })}
                  placeholder="e.g. bewerbung, application"
                  className={styles.filterPattern}
                />

                <label className={styles.checkboxLabel}>
                  <input
                    type="checkbox"
                    checked={filter.is_regex}
                    onChange={(e) => updateFilter(filter.id, { is_regex: e.target.checked })}
                  />
                  Regex
                </label>

                <label className={styles.checkboxLabel}>
                  <input
                    type="checkbox"
                    checked={filter.is_active}
                    onChange={(e) => updateFilter(filter.id, { is_active: e.target.checked })}
                  />
                  Active
                </label>

                <button 
                  onClick={() => deleteFilter(filter.id)}
                  className={styles.btnIconDanger}
                  title="Delete filter"
                >
                  <TrashIcon className={styles.icon} />
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ═══ SECTION 4: Telegram Notifications ═══ */}
      <section className={styles.section}>
        <h2>Telegram Notifications</h2>

        <label className={styles.checkboxLabel}>
          <input
            type="checkbox"
            checked={profile.telegram_enabled}
            onChange={(e) => saveProfile({ telegram_enabled: e.target.checked })}
          />
          Enable Telegram notifications
        </label>

        {profile.telegram_enabled && (
          <>
            <div className={styles.formGroup}>
              <label>Bot Token</label>
              <input
                type="text"
                value={profile.telegram_bot_token || ''}
                onChange={(e) => setProfile({ ...profile, telegram_bot_token: e.target.value })}
                onBlur={() => saveProfile({ telegram_bot_token: profile.telegram_bot_token })}
                placeholder="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
              />
            </div>

            <div className={styles.formGroup}>
              <label>Chat ID</label>
              <input
                type="text"
                value={profile.telegram_chat_id || ''}
                onChange={(e) => setProfile({ ...profile, telegram_chat_id: e.target.value })}
                onBlur={() => saveProfile({ telegram_chat_id: profile.telegram_chat_id })}
                placeholder="123456789"
              />
            </div>

            <a 
              href="https://core.telegram.org/bots#how-do-i-create-a-bot" 
              target="_blank" 
              rel="noopener noreferrer"
              className={styles.helpLink}
            >
              How to get Bot Token and Chat ID →
            </a>
          </>
        )}
      </section>

      {/* ═══ SECTION 5: GDPR ═══ */}
      <section className={`${styles.section} ${styles.dangerZone}`}>
        <h2>Data Management</h2>
        
        <div className={styles.formGroup}>
          <label>Export Your Data</label>
          <p>Download all your application data as JSON.</p>
          <button className={styles.btnSecondary}>Export Data</button>
        </div>

        <div className={styles.formGroup}>
          <label>Delete Account</label>
          <p className={styles.dangerText}>
            This will permanently delete your account and all associated data. 
            This action cannot be undone.
          </p>
          <button className={styles.btnDanger}>Delete Account</button>
        </div>
      </section>
    </div>
  );
}

