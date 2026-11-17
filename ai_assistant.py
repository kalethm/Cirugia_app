import json
import pandas as pd
from typing import Dict, Any
import streamlit as st
from groq import Groq

class ClinicalAIAssistant:
    """
    Asistente AI para análisis de historias clínicas usando Groq (GRATIS)
    Modelo fijo: openai/gpt-oss-20b
    """

    def __init__(self, api_key: str = None):
        if api_key is None:
            api_key = self._get_api_key()

        if not api_key:
            raise ValueError(
                "❌ API Key de Groq no configurada.\n\n"
                "🔧 Para configurarla:\n"
                "1. Crea .streamlit/secrets.toml con:\n"
                "   groq_api_key = 'gsk_tu_key_aqui'\n"
                "2. O configura la variable de entorno GROQ_API_KEY\n"
                "3. Obtén tu API key gratis en: https://console.groq.com"
            )

        self.client = Groq(api_key=api_key)
        self.model = "openai/gpt-oss-20b"  # MODELO FIJO

    def _get_api_key(self) -> str:
        try:
            return st.secrets["groq_api_key"]
        except:
            pass
        import os
        return os.environ.get("GROQ_API_KEY")

    def prepare_clinical_context(self, paciente_info: Dict, cirugias: pd.DataFrame,
                                 historia: pd.DataFrame) -> str:
        context = f"""
┌─────────────────────────────────────────┐
│ DATOS DEL PACIENTE                       │
└─────────────────────────────────────────┘
• Nombre: {paciente_info.get('nombre_paciente', 'No disponible')}
• Documento: {paciente_info.get('tipo_documento', '')} {paciente_info.get('numero_documento', '')}
• Sexo: {paciente_info.get('sexo', 'No disponible')}
• Fecha nacimiento: {paciente_info.get('fecha_nacimiento', 'No disponible')}
• Institución: {paciente_info.get('institucion', 'No disponible')}
"""
        if not cirugias.empty:
            context += """
┌─────────────────────────────────────────┐
│ CIRUGÍAS REALIZADAS                     │
└─────────────────────────────────────────┘"""
            for idx, (_, row) in enumerate(cirugias.iterrows(), 1):
                checklist_status = "✅ COMPLETO" if self._checklist_completo(row) else "❌ INCOMPLETO"
                pdf_status = "✅" if str(row.get('pdf_checklist', '')).strip() else "❌"
                context += f"""

🔹 Cirugía #{int(row.get('id', idx))}
   📅 Fecha: {row.get('fecha_cirugia', 'No disponible')}
   🔪 Procedimiento: {row.get('procedimiento', 'No disponible')}
   📋 Checklist: {checklist_status}
   📄 PDF generado: {pdf_status}
"""
                preop_data = self._parse_json_safe(row.get('datos_preop'))
                if preop_data:
                    context += """
   ▸ PREOPERATORIO:
"""
                    context += f"     • Identidad confirmada: {'✅' if preop_data.get('identificacion_confirmada') else '❌'}\n"
                    context += f"     • Alergias: {preop_data.get('tiene_alergias', 'No especificado')}\n"
                    if preop_data.get('tiene_alergias') == 'Sí':
                        context += f"     • Detalle alergias: {preop_data.get('detalle_alergias', 'No detallado')}\n"
                    context += f"     • Sitio quirúrgico: {preop_data.get('sitio_quirurgico', 'No especificado')}\n"
                    context += f"     • Consentimiento informado: {'✅' if preop_data.get('consentimiento_informado') else '❌'}\n"
                    context += f"     • Ayuno adecuado: {'✅' if preop_data.get('ayuno_adecuado') else '❌'}\n"
                    context += f"     • Instrumental verificado: {'✅' if preop_data.get('instrumental_verificado') else '❌'}\n"

                intraop_data = self._parse_json_safe(row.get('datos_intraop'))
                if intraop_data:
                    context += """
   ▸ INTRAOPERATORIO:
"""
                    context += f"     • Esterilidad: {'✅' if intraop_data.get('esterilidad_campo') else '❌'}\n"
                    context += f"     • Posición: {intraop_data.get('posicion_paciente', 'No especificada')}\n"
                    context += f"     • Horario: {intraop_data.get('hora_inicio', '?')} - {intraop_data.get('hora_fin', '?')}\n"
                    context += f"     • Medicación: {intraop_data.get('medicacion_tipo', 'No')}\n"
                    if intraop_data.get('hubo_incidencias') == 'Sí':
                        context += f"     • ⚠️ INCIDENCIAS: {intraop_data.get('detalle_incidencias', 'No detalladas')}\n"

                postop_data = self._parse_json_safe(row.get('datos_postop'))
                if postop_data:
                    context += """
   ▸ POSTOPERATORIO:
"""
                    context += f"     • Control dolor: {'✅' if postop_data.get('dolor_ok') else '❌'}\n"
                    context += f"     • Conciencia: {'✅' if postop_data.get('conciencia_ok') else '❌'}\n"
                    context += f"     • Signos vitales: {postop_data.get('signos_vitales', 'No registrados')}\n"

        if not historia.empty:
            context += """
┌─────────────────────────────────────────┐
│ HISTORIAL CLÍNICO                       │
└─────────────────────────────────────────┘"""
            for idx, (_, row) in enumerate(historia.iterrows(), 1):
                context += f"""

📝 Registro #{int(row.get('id', idx))}
   📅 Fecha: {row.get('fecha_registro', 'No disponible')}
   📋 Tipo: {row.get('tipo_registro', 'No disponible')}
   🔍 Motivo: {row.get('motivo', 'No disponible')}
   💉 Diagnóstico: {row.get('diagnostico', 'No disponible')}
   📖 Antecedentes: {row.get('antecedentes', 'No especificados')}
   👀 Observaciones: {row.get('observaciones', 'No especificadas')}
"""
        context += "\n" + "─" * 50 + "\n"
        return context

    def _checklist_completo(self, row: pd.Series) -> bool:
        return all([
            row.get('preop_completa', False),
            row.get('firmas_preop_completas', False),
            row.get('intraop_completa', False),
            row.get('postop_completa', False)
        ])

    def _parse_json_safe(self, value):
        if pd.isna(value) or value == "":
            return None
        try:
            if isinstance(value, str):
                return json.loads(value)
            elif isinstance(value, dict):
                return value
            return None
        except:
            return None

    def ask_question(self, context: str, question: str) -> Dict[str, Any]:
        if not self.client:
            return {"error": "Cliente no inicializado", "response": None}

        system_prompt = """Eres un asistente médico especializado en análisis de historias clínicas.
Responde SIEMPRE en español. Sé conciso pero completo. No des consejos médicos.
Cita datos del contexto. Señala alertas pero no diagnostiques."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"""CONTEXTO CLÍNICO:

{context}

PREGUNTA:
{question}

Analiza el contexto y responde profesionalmente."""}
                ],
                temperature=0.2,
                max_tokens=2000,
                top_p=0.9
            )

            return {
                "response": response.choices[0].message.content,
                "tokens_used": response.usage.total_tokens,
                "model": self.model,
                "provider": "Groq (Gratuito)"
            }

        except Exception as e:
            error_msg = str(e)
            if "rate_limit" in error_msg.lower():
                return {"error": "⏳ Límite de velocidad. Espera unos segundos.", "response": None}
            elif "401" in error_msg or "403" in error_msg:
                return {"error": "🔑 API Key inválida. Revisa en https://console.groq.com", "response": None}
            else:
                return {"error": f"Error: {error_msg}", "response": None}

    def summarize_clinical_record(self, context: str) -> Dict[str, Any]:
        if not self.client:
            return {"error": "Cliente no inicializado", "response": None}

        system_prompt = """Genera un resumen clínico en español con estas secciones:
📋 DATOS DEL PACIENTE
🔪 PROCEDIMIENTOS
⚠️ ALERTAS (alergias, incidencias, consentimientos)
📊 ESTADO DE CHECKLISTS
📈 EVOLUCIÓN
🔍 PENDIENTES"""

        try:
            # ✅ USA EL MISMO MODELO FIJO: openai/gpt-oss-20b
            response = self.client.chat.completions.create(
                model=self.model,  # <-- CORREGIDO: usa self.model
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Genera un resumen clínico de:\n\n{context}"}
                ],
                temperature=0.3,
                max_tokens=2500
            )

            return {
                "response": response.choices[0].message.content,
                "tokens_used": response.usage.total_tokens,
                "provider": "Groq (Gratuito)"
            }

        except Exception as e:
            return {"error": f"Error al generar resumen: {str(e)}", "response": None}

    def ask_central_esterilizacion(self, context: str, historial: list) -> Dict[str, Any]:
        system_prompt = """Eres el asistente de la central de esterilización de una institución de salud.
Responde SIEMPRE en español, de forma breve y directa, usando solo los datos entregados.
Cita códigos de set, números de carga, lotes y fechas. Usa listas o tablas cortas cuando ayuden.
Si el dato no está en la información, dilo; no inventes registros ni cifras.
Solo consultas: no puedes modificar registros."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": f"{system_prompt}\n\nDATOS ACTUALES DE LA CENTRAL:\n\n{context}"},
                    *historial,
                ],
                temperature=0.2,
                max_tokens=2000,
                reasoning_effort="low"
            )

            return {
                "response": response.choices[0].message.content,
                "tokens_used": response.usage.total_tokens,
                "provider": "Groq (Gratuito)"
            }

        except Exception as e:
            error_msg = str(e)
            if "rate_limit" in error_msg.lower():
                return {"error": "⏳ Límite de velocidad. Espera unos segundos.", "response": None}
            elif "401" in error_msg or "403" in error_msg:
                return {"error": "🔑 API Key inválida. Revisa en https://console.groq.com", "response": None}
            else:
                return {"error": f"Error: {error_msg}", "response": None}
