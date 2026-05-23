/**
 * Style presets — one-click templates that fill brief + settings.
 *
 * Each preset = a starter brief skeleton + recommended settings (model,
 * duration, aspect, audio mode). User clicks → form pre-filled → tweak brief →
 * Generate. Designed for VN content creators who don't know how to write
 * cinematic briefs from scratch (most users).
 */

import type { VideoModel, AspectRatio, AudioMode } from '@/lib/types/backend';
import type { LucideIcon } from 'lucide-react';
import { Sparkles, ShoppingBag, Mic2, Film, Camera, Coffee } from 'lucide-react';

export interface StylePreset {
  id: string;
  label_vn: string;
  description_vn: string;
  icon: LucideIcon;
  accent: 'magenta' | 'orange' | 'cyan' | 'yellow' | 'green';
  brief_template: string;
  settings: {
    model: VideoModel;
    duration_s: number;
    aspect_ratio: AspectRatio;
    audio_mode: AudioMode;
  };
}

export const STYLE_PRESETS: StylePreset[] = [
  {
    id: 'ugc_casual',
    label_vn: 'UGC Casual',
    description_vn: 'Vlog-style POV iPhone — TikTok native feel',
    icon: Camera,
    accent: 'magenta',
    brief_template: [
      'UGC iPhone handheld, một cô gái Việt 25 tuổi mặc áo thun trắng oversized.',
      'Cô đang ngồi ở quán cafe có ánh sáng cửa sổ tự nhiên golden hour.',
      'Cô cầm sản phẩm lên review tự nhiên, nét mặt vui vẻ, ánh mắt thân thiện camera.',
      'Camera handheld nhẹ, không quá rung. Color grading warm filmic.',
      'Tone: chân thật, gần gũi, không bán hàng kiểu quảng cáo.',
    ].join(' '),
    settings: {
      model: 'seedance_2_0',
      duration_s: 15,
      aspect_ratio: '9:16',
      audio_mode: 'dialogue_vo',
    },
  },
  {
    id: 'cinematic_ad',
    label_vn: 'Cinematic Ad',
    description_vn: 'Premium 35mm film grain — luxury brand feel',
    icon: Film,
    accent: 'yellow',
    brief_template: [
      'Cinematic 35mm film, depth of field shallow, color grading teal & orange.',
      'Camera dolly-in chậm tiết lộ chi tiết sản phẩm như một artifact quý.',
      'Lighting: hard key + soft fill, rim light tạo độ sâu.',
      'Mood: tinh tế, sang trọng, thời gian như chậm lại.',
      'Music cue: orchestral cinematic build, không có dialogue.',
    ].join(' '),
    settings: {
      model: 'seedance_2_0',
      duration_s: 15,
      aspect_ratio: '9:16',
      audio_mode: 'silent_native',
    },
  },
  {
    id: 'talking_head_vn',
    label_vn: 'Talking Head VN',
    description_vn: 'Lip-sync tiếng Việt — presenter close-up',
    icon: Mic2,
    accent: 'cyan',
    brief_template: [
      'Cận cảnh nửa thân trên một presenter Việt nói trực tiếp với camera.',
      'Background blur nhẹ, ánh sáng softbox phía trước + key light bên trái.',
      'Presenter nét mặt thân thiện, gật đầu nhẹ, làm thủ ngữ tự nhiên khi nói.',
      'Outfit: áo sơ mi xanh navy, tóc gọn gàng.',
      'Lip-sync với dialogue VN. Camera static MCU.',
    ].join(' '),
    settings: {
      model: 'wan_2_7',
      duration_s: 10,
      aspect_ratio: '9:16',
      audio_mode: 'dialogue_vo',
    },
  },
  {
    id: 'product_demo',
    label_vn: 'Product Demo',
    description_vn: 'Macro detail + studio lighting — Shopee/Lazada',
    icon: ShoppingBag,
    accent: 'orange',
    brief_template: [
      'Sản phẩm xoay 360 trên bàn studio, background gradient pastel.',
      'Macro close-up cho thấy chi tiết texture, logo, packaging.',
      'Lighting studio softbox đều, không bóng cứng, color accurate.',
      'Camera dolly quanh sản phẩm + push-in CU vào hero feature.',
      'Mood: clean, professional, focus 100% vào sản phẩm.',
    ].join(' '),
    settings: {
      model: 'seedance_2_0_fast',
      duration_s: 10,
      aspect_ratio: '1:1',
      audio_mode: 'silent_native',
    },
  },
  {
    id: 'asmr_lifestyle',
    label_vn: 'ASMR Lifestyle',
    description_vn: 'Soft ambient — beauty/skincare unboxing',
    icon: Coffee,
    accent: 'magenta',
    brief_template: [
      'Tay nhẹ nhàng mở hộp sản phẩm trên bàn gỗ warm tone.',
      'Lighting: window light side mềm, hơi flare nhẹ. Color grading warm pastel.',
      'Camera ECU vào tay, macro lens độ sâu shallow.',
      'Mood: chậm rãi, êm dịu, gợi cảm giác chăm sóc bản thân.',
      'Audio: SFX ambient — paper rustle, soft click, breathing — không có dialogue.',
    ].join(' '),
    settings: {
      model: 'seedance_2_0',
      duration_s: 12,
      aspect_ratio: '9:16',
      audio_mode: 'asmr_macro',
    },
  },
  {
    id: 'budget_quick',
    label_vn: 'Budget Quick',
    description_vn: 'Cheapest gen — A/B test ý tưởng nhanh',
    icon: Sparkles,
    accent: 'green',
    brief_template: [
      'Simple shot, một nhân vật chính ở center frame, background đơn giản.',
      'Camera MS static, lighting tự nhiên ban ngày.',
      'Action ngắn 1-2 beat, đủ thể hiện ý tưởng chính.',
    ].join(' '),
    settings: {
      model: 'vidu_q3',
      duration_s: 8,
      aspect_ratio: '9:16',
      audio_mode: 'silent_native',
    },
  },
];

export function getStylePreset(id: string): StylePreset | undefined {
  return STYLE_PRESETS.find((p) => p.id === id);
}
