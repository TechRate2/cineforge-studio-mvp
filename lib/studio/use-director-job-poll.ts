'use client';
import { useEffect, useRef, useState } from 'react';
import { fetchDirectorJob } from './director-job-api';

export interface DirectorJobStatus {
  job_id: string;
  status: 'pending' | 'planning' | 'dry_run' | 'rendering' | 'assembling' | 'uploading' | 'graph_executing' | 'graph_idle' | 'done' | 'failed' | 'cancelled';
  progress: number;
  current_step?: string;
  output_path?: string | null;
  output_url?: string | null;
  error_message?: string | null;
  elapsed_s?: number;
  feedback_summary?: {
    feedback_count?: number;
    latest_feedback_at?: string | null;
    latest_rating?: string | null;
    issue_counts?: Record<string, number>;
    rating_counts?: Record<string, number>;
    has_negative_feedback?: boolean;
    has_blocking_issue?: boolean;
    recommended_next_action?: string;
  };
  longform_progress?: {
    segment_count?: number;
    completed_segments?: number;
    current_segment_id?: string | null;
    last_event?: Record<string, unknown>;
    events?: Array<Record<string, unknown>>;
  };
  longform_render_execution?: {
    status?: string;
    qa_reports?: Array<{
      shot_id?: string;
      status?: string;
      warnings?: string[];
      errors?: string[];
      consistency_score?: number | null;
      consistency_policy_action?: string | null;
      consistency_warnings?: string[];
      visual_consistency?: {
        status?: string;
        action?: string;
        risk_level?: string;
        overall_score?: number | null;
        signal_source?: string;
        warnings?: string[];
        errors?: string[];
        metrics?: Record<string, number>;
        missing_signals?: string[];
      } | null;
    }>;
  } | null;
  assembly_result?: {
    status?: string;
    final_video_url?: string | null;
    final_video_path?: string | null;
    storage_bucket?: string | null;
    storage_key?: string | null;
    storage_type?: string | null;
    storage_access_strategy?: string | null;
    storage_delivery_url?: string | null;
    storage_cdn_url?: string | null;
    storage_is_public?: boolean | null;
    storage_public_url?: string | null;
    storage_presigned_url?: string | null;
    storage_presigned_expires_s?: number | null;
    storage_presigned_expires_at?: string | null;
    storage_refresh_supported?: boolean | null;
    error?: string | null;
  };
  editor_meta?: {
    caption_vn?: string;
    caption_en?: string;
    hashtags_vn?: string[];
    hashtags_en?: string[];
    best_posting_time_vn?: string;
    distribution_package?: {
      target_platform?: string;
      target_market?: string;
      niche?: string;
      runtime_bucket?: string;
      caption_primary?: string;
      caption_secondary?: string;
      title_hint?: string;
      description_hint?: string;
      cover_frame_cue?: string;
      cta_style?: string;
      posting_hint?: string;
      hashtag_primary?: string[];
      platform_notes?: string[];
      checks?: Array<{ name?: string; status?: string; detail?: string }>;
    };
  };
  autonomous_meta?: {
    auto_pin_selection?: {
      enabled?: boolean;
      mode?: string;
      explicit_pin_ids?: string[];
      auto_selected_pin_ids?: string[];
      count?: number;
      candidates_considered?: number;
      selected?: Array<{
        pin_id?: string;
        asset_id?: string;
        role?: string;
        priority?: number;
        target_market?: string;
        niche?: string;
        series_key?: string;
        score?: number;
        reasons?: string[];
      }>;
      policy?: string;
    };
    autonomous_preflight?: {
      status?: 'pass' | 'warn' | 'fail' | string;
      score?: number;
      render_allowed?: boolean;
      manual_review_recommended?: boolean;
      next_action?: string;
      warnings?: string[];
      hard_failures?: string[];
      responsible_content_gate?: ResponsibleContentGate;
      script_asset_sop?: ScriptAssetSop;
      long_form_execution_gate?: LongFormExecutionGate;
      checks?: Array<{
        name?: string;
        status?: string;
        severity?: string;
        detail?: string;
      }>;
      producer_story_critic?: {
        schema_version?: string;
        status?: 'pass' | 'warn' | 'fail' | string;
        score?: number;
        niche?: string;
        target_market?: string;
        target_platform?: string;
        top_issues?: string[];
        repair_hint?: string;
        dimensions?: Array<{
          name?: string;
          status?: string;
          score?: number;
          issues?: string[];
          detail?: string;
        }>;
      };
      niche_execution_rubric?: NicheExecutionRubric;
      continuity_handoff_policy?: {
        schema_version?: string;
        duration_s?: number;
        runtime_class?: string;
        shot_count?: number;
        required_handoffs?: number;
        active_handoffs?: number;
        missing_required_handoffs?: number;
        intentional_cuts?: number;
        score?: number;
        summary?: string;
      };
      cross_shot_diagnostic?: {
        schema_version?: string;
        status?: 'pass' | 'warn' | 'fail' | string;
        score?: number;
        shot_count?: number;
        duration_s?: number;
        runtime_class?: string;
        top_issues?: string[];
        repair_hint?: string;
        dimensions?: Array<{
          name?: string;
          status?: string;
          score?: number;
          issues?: string[];
          detail?: string;
        }>;
      };
      reference_sufficiency?: ReferenceSufficiency;
      screenplay_scene_lint?: {
        status?: 'pass' | 'warn' | 'fail' | string;
        score?: number;
        scene_count?: number;
        failed_scene_count?: number;
        warned_scene_count?: number;
        top_issues?: string[];
        scene_reports?: Array<{
          scene_id?: string;
          status?: string;
          issues?: string[];
          warnings?: string[];
          repair_hint?: string;
        }>;
      };
      seedance_shot_lint?: {
        status?: 'pass' | 'warn' | 'fail' | string;
        score?: number;
        shot_count?: number;
        failed_shot_count?: number;
        warned_shot_count?: number;
        failed_shots?: string[];
        warned_shots?: string[];
        top_issues?: string[];
        shot_reports?: Array<{
          shot_id?: string;
          status?: string;
          hard_failures?: string[];
          warnings?: string[];
          repair_hint?: string;
        }>;
      };
    };
    production_decision?: {
      decision?: {
        niche?: string;
        readiness?: string;
        target_market?: string;
        requested_target_market?: string;
        runtime_class?: string;
        target_duration_s?: number;
        execution_mode?: string;
        graph_required?: boolean;
        dialogue_required?: boolean;
        niche_resolution_review_required?: boolean;
        benchmark_required_before_top_tier_claim?: boolean;
        responsible_review_required?: boolean;
        render_blocked_by_responsible_gate?: boolean;
        primary_model_route?: {
          primary_visual_model?: string;
          continuity_model?: string;
          premium_visual_model?: string;
        };
        dialogue_route_policy?: {
          route_type?: string;
          dialogue_candidate?: string | null;
          target_language?: string;
          requires_benchmark_before_auto_route?: boolean;
        };
        market_inference?: {
          confidence?: number;
          source?: string;
          reasons?: string[];
        };
      };
      responsible_content_gate?: ResponsibleContentGate;
      script_asset_sop?: ScriptAssetSop;
      input_summary?: {
        requested_target_market?: string;
        market_inference?: {
          confidence?: number;
          source?: string;
          reasons?: string[];
        };
        niche_resolution?: {
          selected_niche?: string;
          source?: string;
          confidence?: number;
          fallback_reason?: string | null;
          clarifying_questions?: string[];
          suggested_brief_signals?: string[];
          suggested_brief_template?: string;
          scores?: Array<{
            niche?: string;
            score?: number;
            hits?: string[];
            specific_hits?: string[];
          }>;
        };
      };
      market_playbook?: {
        requested_target_market?: string;
        target_market?: string;
        primary_language?: string;
        caption_language?: string;
        hook_style?: string;
        dialogue_style?: string;
        claim_style?: string;
        seedance_notes?: string[];
      };
      runtime_structure?: {
        runtime_class?: string;
        target_duration_s?: number;
        act_count?: number;
        scene_count?: number;
        chunk_count?: number;
        target_scene_duration_s?: number;
        target_chunk_duration_s?: number;
        shot_budget?: number[];
        act_structure?: Array<{
          act?: number;
          name?: string;
          goal?: string;
          ratio?: number;
        }>;
        render_strategy_hint?: string;
      };
      creative_treatment_search?: {
        selected_treatment_id?: string;
        selected_label?: string;
        selected_score?: number;
        selection_reason?: string;
        candidates?: Array<{
          treatment_id?: string;
          label?: string;
          score?: number;
          risk_level?: string;
          selection_reason?: string;
          director_intent?: string;
          camera_language?: string;
          edit_rhythm?: string;
          reference_policy?: string;
          suggested_hook_move?: string;
          duration_strategy?: string;
          risks?: string[];
          reasons?: string[];
        }>;
        policy?: string[];
      };
      model_route_strategy?: {
        summary?: {
          route_mode?: string;
          primary_visual_model?: string;
          continuity_model?: string;
          premium_visual_model?: string;
          draft_visual_model?: string;
          runtime_class?: string;
        };
        seedance_execution?: {
          unit_duration_s?: number;
          estimated_units?: number;
          single_call_allowed?: boolean;
          requires_reference_to_video?: boolean;
          premium_ref_for_hero_shots?: boolean;
          long_form_method?: string;
        };
        active_routes?: Array<{
          model_key?: string;
          role?: string;
          status?: string;
          why?: string;
          use_when?: string;
        }>;
        benchmark_locked_candidates?: Array<{
          model_key?: string;
          role?: string;
          fit?: string;
          status?: string;
          why?: string;
          benchmark_needed?: string[];
        }>;
        route_locks?: string[];
        promotion_policy?: string[];
      };
      seedance_reference_allocation?: {
        fits_seedance_caps?: boolean;
        warnings?: string[];
        reference_sufficiency?: ReferenceSufficiency;
        image_role_plan?: Array<{ tag?: string; role?: string; job?: string; priority?: number }>;
        video_role_plan?: Array<{ tag?: string; role?: string; job?: string; priority?: number }>;
        audio_role_plan?: Array<{ tag?: string; role?: string; job?: string; priority?: number }>;
        per_shot_policy?: Array<{ shot_type?: string; use_refs?: string[]; goal?: string }>;
        long_form_handoff_policy?: {
          enabled?: boolean;
          first_scene?: string;
          later_scenes?: string;
          retry_scope?: string;
        };
      };
      seedance_segment_inspector?: {
        schema_version?: string;
        mode?: string;
        runtime_class?: string;
        target_duration_s?: number;
        preview_segment_count?: number;
        estimated_total_units?: number;
        reference_job_count?: number;
        unit_contract?: {
          duration_s?: number[];
          rule?: string;
          long_form_rule?: string;
        };
        segments?: Array<{
          segment_id?: string;
          source_scene_id?: string;
          unit_index?: number;
          target_duration_s?: number;
          shot_type?: string;
          purpose?: string;
          model_route?: string;
          use_refs?: string[];
          continuity_anchor?: string;
          prompt_blocks?: {
            reference_jobs?: string[];
            timeline?: string;
            story_intent?: string;
            action?: string;
            camera?: string;
            sound?: string;
            constraints?: string[];
          };
          qa_checks?: string[];
        }>;
        operator_policy?: string[];
      };
      seedance_prompt_formula?: {
        schema_version?: string;
        source_pattern?: string;
        niche?: string;
        runtime_class?: string;
        target_duration_s?: number;
        target_market?: string;
        target_platform?: string;
        formula?: string[];
        reference_job_policy?: {
          required_reference_jobs?: string[];
          current_reference_jobs?: Array<{ tag?: string; role?: string; job?: string }>;
          assignment_rule?: string;
          slot_priority?: string[];
        };
        niche_template?: {
          story_intent?: string;
          action?: string;
          camera?: string;
          sound?: string;
        };
        unit_prompt_skeleton?: string[];
        rewrite_rules?: string[];
        benchmark_policy?: string[];
      };
      autonomous_input_upgrade_plan?: {
        schema_version?: string;
        niche?: string;
        runtime_class?: string;
        target_market?: string;
        renderable_now?: boolean;
        top_tier_ready?: boolean;
        route_confidence?: string;
        current_reference_counts?: Record<string, number>;
        minimum_to_attempt?: Record<string, number>;
        best_quality_targets?: Record<string, number>;
        missing_minimum?: Record<string, number>;
        missing_to_best?: Record<string, number>;
        priority_actions?: Array<{
          priority?: string;
          kind?: string;
          action?: string;
          why?: string;
        }>;
        user_message?: string;
        auto_mode_policy?: string[];
      };
      reference_sufficiency?: ReferenceSufficiency;
      niche_execution_rubric?: NicheExecutionRubric;
      niche_production_recipe?: NicheProductionRecipe;
      long_form_execution_gate?: LongFormExecutionGate;
      route_quality_scorecard?: {
        schema_version?: string;
        route_key?: {
          model_key?: string;
          niche?: string;
          runtime_class?: string;
          target_market?: string;
        };
        launch_tier?: string;
        auto_route_allowed?: boolean;
        top_tier_claim_allowed?: boolean;
        requires_human_review?: boolean;
        requires_graph_executor?: boolean;
        requires_benchmark_before_premium_claim?: boolean;
        blocking_reasons?: string[];
        evidence_status?: {
          exact_route_promoted?: boolean;
          total_results_considered?: number;
          promoted_route_count?: number;
          reference_top_tier_ready?: boolean;
          reference_score?: number;
        };
        next_benchmark_batch?: Array<{
          kind?: string;
          model_key?: string;
          niche?: string;
          runtime_class?: string;
          target_market?: string;
          minimum_runs?: number;
          evidence?: string[];
        }>;
        operator_policy?: string[];
      };
      cinematic_grammar?: {
        schema_version?: string;
        niche?: string;
        runtime_class?: string;
        target_market?: string;
        treatment_id?: string;
        story_archetype?: {
          name?: string;
          promise?: string;
          turn?: string;
          long_form_rule?: string;
        };
        shot_palette?: Array<{ role?: string; camera?: string; purpose?: string }>;
        transition_logic?: string[];
        editor_pacing?: { tempo?: string; rule?: string; average_shot_s?: string };
        sound_strategy?: {
          primary_texture?: string;
          dialogue_register?: string;
          caption_rule?: string;
          sync_rule?: string;
        };
        prompt_directives?: string[];
        anti_patterns?: string[];
        qa_questions?: string[];
      };
      niche_runtime_director?: {
        schema_version?: string;
        niche?: string;
        target_market?: string;
        target_platform?: string;
        runtime_class?: string;
        target_duration_s?: number;
        director_mode?: string;
        story_shape?: {
          rule?: string;
          niche_beat_flow?: string[];
          runtime_structure?: string[];
          payoff_requirement?: string;
        };
        opening_contract?: {
          first_3s?: string;
          alternate_hooks?: string[];
          must_show?: string;
          avoid?: string;
          long_form_extra?: string;
        };
        scene_architecture?: {
          act_count?: number;
          scene_count?: number;
          chunk_count?: number;
          target_scene_duration_s?: number;
          target_chunk_duration_s?: number;
          long_form_method?: string;
        };
        seedance_unit_doctrine?: {
          estimated_units?: number;
          target_unit_duration_s?: number;
          unit_duration_contract_s?: number[];
          single_call_allowed?: boolean;
          single_action_rule?: string;
          continuity_method?: string;
          retry_scope?: string;
        };
        editorial_rhythm?: {
          primary_rhythm?: string;
          camera_palette?: string[];
          audio_texture?: string;
        };
        reference_contract?: {
          minimum?: string[];
          current_refs?: Record<string, number>;
          missing_for_best_quality?: string[];
          role_rule?: string;
        };
        market_localization?: {
          primary_language?: string;
          caption_language?: string;
          hook_style?: string;
          dialogue_style?: string;
          claim_style?: string;
          rule?: string;
        };
        qa_focus?: string[];
        risk_register?: string[];
      };
      long_form_scene_preview?: {
        enabled?: boolean;
        scene_count?: number;
        estimated_seedance_units?: number;
        logline?: string;
        editor_promise?: string;
        continuity_contract?: string[];
        scene_blueprints?: Array<{
          scene_id?: string;
          index?: number;
          act?: number;
          duration_s?: number;
          purpose?: string;
          dramatic_question?: string;
          visual_hook?: string;
          continuity_anchor?: string;
          handoff_to_next?: string;
          conflict?: string;
          turning_point?: string;
          dialogue_or_vo_intent?: string;
          seedance_render_plan?: {
            estimated_units?: number;
            target_unit_duration_s?: number;
            continuity_mode?: string;
            retry_scope?: string;
            unit_duration_contract_s?: number[];
          };
          reference_priorities?: string[];
          qa_focus?: string[];
        }>;
      };
      qa_gates?: string[];
    };
    scene_memory_pack?: {
      schema_version?: string;
      runtime_class?: string;
      target_duration_s?: number;
      scene_count?: number;
      shot_count?: number;
      scene_memory?: Array<{
        scene_id?: string;
        index?: number;
        act?: number;
        duration_s?: number;
        purpose?: string;
        dramatic_question?: string;
        opening_image_intent?: string;
        closing_image_intent?: string;
        conflict?: string;
        turning_point?: string;
        continuity_anchor?: string;
        handoff_to_next?: string;
        reference_priorities?: string[];
        seedance_unit_policy?: {
          target_unit_duration_s?: number;
          estimated_units?: number;
          max_unit_duration_s?: number;
          single_action_rule?: string;
        };
        shot_ids?: string[];
        first_shot_id?: string | null;
        last_shot_id?: string | null;
        previous_scene_final_frame_required?: boolean;
        next_scene_bridge_required?: boolean;
        qa_focus?: string[];
      }>;
      shot_scene_map?: Array<{
        shot_id?: string;
        scene_id?: string;
        scene_index?: number;
        role_in_scene?: string;
        previous_shot_id?: string | null;
        reference_indices?: number[];
      }>;
      bridge_policy?: {
        runtime_requires_scene_bridges?: boolean;
        bridge_count?: number;
        bridges?: Array<{
          from_scene_id?: string;
          to_scene_id?: string;
          source_last_shot_id?: string | null;
          target_first_shot_id?: string | null;
          preferred_bridge?: string;
          repair_if_drift?: string;
          risk?: string;
        }>;
      };
      qa_contract?: {
        per_scene?: string[];
        whole_film?: string[];
      };
      producer_note?: string;
    };
  };
}

export interface LongFormExecutionGate {
  schema_version?: string;
  enabled?: boolean;
  status?: 'pass' | 'warn' | 'fail' | string;
  runtime_class?: string;
  target_duration_s?: number;
  render_route?: string;
  default_route_allowed?: boolean;
  graph_executor_ready?: boolean;
  long_form_claim_allowed?: boolean;
  blockers?: string[];
  warnings?: string[];
  requirements?: Array<{
    name?: string;
    status?: string;
    detail?: string;
  }>;
  execution_contract?: {
    unit_duration_s?: number[];
    target_chunk_duration_s?: number;
    graph_node_count?: number;
    graph_shot_count?: number;
    graph_qa_count?: number;
    shot_count?: number;
    scene_count?: number;
    scene_bridge_count?: number;
    active_handoffs?: number;
    required_handoffs?: number;
    doctrine?: string[];
  };
  required_before_default?: string[];
  next_action?: string;
}

export interface ResponsibleContentGate {
  schema_version?: string;
  status?: 'pass' | 'warn' | 'fail' | string;
  render_allowed?: boolean;
  manual_review_required?: boolean;
  hard_blockers?: string[];
  review_flags?: string[];
  matches?: Record<string, string[]>;
  rewrite_guidance?: string[];
  policy?: string[];
}

export interface ScriptAssetSop {
  schema_version?: string;
  enabled?: boolean;
  runtime_class?: string;
  niche?: string;
  target_market?: string;
  source_pattern?: string;
  current_reference_coverage?: Record<string, number>;
  asset_groups?: {
    characters?: ScriptAssetItem[];
    locations?: ScriptAssetItem[];
    props_or_products?: ScriptAssetItem[];
    style_anchors?: ScriptAssetItem[];
    voice_or_dialogue?: ScriptAssetItem[];
  };
  missing_before_top_tier?: string[];
  pre_render_steps?: string[];
  policy?: string[];
}

export interface ScriptAssetItem {
  role?: string;
  name?: string;
  priority?: string;
  required_views?: string[];
  pin_policy?: string;
}

export interface NicheProductionRecipe {
  schema_version?: string;
  niche?: string;
  runtime_class?: string;
  target_duration_s?: number;
  target_market?: string;
  target_platform?: string;
  director_recipe?: {
    opening_move?: string;
    story_engine?: string;
    framing_language?: string[];
    edit_shape?: string;
    sound_shape?: string;
  };
  reference_recipe?: {
    priority_order?: string[];
    current_refs?: Record<string, number>;
    minimum_to_attempt?: Record<string, number>;
    best_quality_refs?: Record<string, number>;
    assignment_rule?: string;
  };
  duration_recipe?: {
    runtime_class?: string;
    target_unit_duration_s?: number;
    estimated_seedance_units?: number;
    scene_count?: number;
    chunk_count?: number;
    rule?: string;
  };
  seedance_prompt_recipe?: {
    block_order?: string[];
    must_include?: string[];
    avoid?: string[];
    shot_unit_rule?: string;
    multi_shot_rule?: string;
  };
  qa_recipe?: {
    hard_checks?: string[];
    review_checks?: string[];
    common_failure_modes?: string[];
    retry_scope?: string;
  };
  operator_note?: string;
}

export interface ReferenceSufficiency {
  schema_version?: string;
  status?: 'pass' | 'warn' | 'fail' | string;
  score?: number;
  top_tier_ready?: boolean;
  render_blocking?: boolean;
  runtime_class?: string;
  target_duration_s?: number;
  niche?: string;
  target_market?: string;
  reference_counts?: {
    images?: number;
    videos?: number;
    audios?: number;
    pinned_assets?: number;
  };
  minimum_contract?: string[];
  optimal_contract?: string[];
  checks?: Array<{
    name?: string;
    status?: string;
    detail?: string;
    recommendation?: string;
  }>;
  missing_for_top_tier?: string[];
  next_best_action?: string;
}

export interface NicheExecutionRubric {
  schema_version?: string;
  status?: 'pass' | 'warn' | 'fail' | string;
  score?: number;
  niche?: string;
  target_market?: string;
  runtime_class?: string;
  best_for?: string;
  required_hook_moves?: string[];
  required_beat_flow?: string[];
  camera_grammar?: string[];
  audio_texture?: string;
  quality_bar?: string[];
  safety_rules?: string[];
  dimensions?: Array<{
    name?: string;
    status?: string;
    score?: number;
    issues?: string[];
    detail?: string;
  }>;
  top_issues?: string[];
  next_best_action?: string;
}

/** V5.1 — job stuck timeout (15 min). When exceeded, polling stops and
 *  `timedOut` becomes true so the UI can prompt the user to check History
 *  or manually cancel. Render rarely exceeds 5 min on healthy AtlasCloud. */
const STUCK_TIMEOUT_MS = 15 * 60 * 1000;

export function useDirectorJobPoll(jobId: string | null, intervalMs: number = 2500) {
  const [job, setJob] = useState<DirectorJobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [timedOut, setTimedOut] = useState(false);
  const startedAtRef = useRef<number | null>(null);

  useEffect(() => {
    if (!jobId) {
      setJob(null);
      setTimedOut(false);
      startedAtRef.current = null;
      return;
    }
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | null = null;
    startedAtRef.current = Date.now();
    setTimedOut(false);

    const tick = async () => {
      if (!alive) return;
      // V5.1 — abort polling if job has been alive past stuck threshold
      const elapsed = Date.now() - (startedAtRef.current ?? Date.now());
      if (elapsed > STUCK_TIMEOUT_MS) {
        setTimedOut(true);
        return;
      }
      try {
        const res = await fetchDirectorJob(jobId);
        if (!alive) return;
        setJob(res);
        setError(null);
        const status = res.status as DirectorJobStatus['status'];
        if (status === 'done' || status === 'failed' || status === 'cancelled') {
          return;
        }
        timer = setTimeout(tick, intervalMs);
      } catch (e) {
        if (!alive) return;
        setError(e instanceof Error ? e.message : String(e));
        timer = setTimeout(tick, intervalMs * 2);
      }
    };
    tick();
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, [jobId, intervalMs]);

  return { job, error, timedOut };
}
