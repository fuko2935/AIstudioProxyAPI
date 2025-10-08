# --- browser_utils/script_manager.py ---
# Tampermonkey betik yönetim modülü - dinamik yükleme ve enjeksiyon

import os
import json
import logging
from typing import Dict, List, Optional, Any
from playwright.async_api import Page as AsyncPage

logger = logging.getLogger("AIStudioProxyServer")

class ScriptManager:
    """Tampermonkey betik yöneticisi - betikleri dinamik biçimde yükler ve enjekte eder"""
    
    def __init__(self, script_dir: str = "browser_utils"):
        self.script_dir = script_dir
        self.loaded_scripts: Dict[str, str] = {}
        self.model_configs: Dict[str, List[Dict[str, Any]]] = {}
        
    def load_script(self, script_name: str) -> Optional[str]:
        """Belirtilen JavaScript betik dosyasını yükler"""
        script_path = os.path.join(self.script_dir, script_name)
        
        if not os.path.exists(script_path):
            logger.error(f"Betik dosyası bulunamadı: {script_path}")
            return None
            
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                script_content = f.read()
                self.loaded_scripts[script_name] = script_content
                logger.info(f"Betik yüklendi: {script_name}")
                return script_content
        except Exception as e:
            logger.error(f"Betik yüklenemedi {script_name}: {e}")
            return None

    def load_model_config(self, config_path: str) -> Optional[List[Dict[str, Any]]]:
        """Model yapılandırma dosyasını yükler"""
        if not os.path.exists(config_path):
            logger.warning(f"Model yapılandırma dosyası bulunamadı: {config_path}")
            return None
            
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                models = config_data.get('models', [])
                self.model_configs[config_path] = models
                logger.info(f"Model yapılandırması yüklendi: {len(models)} model")
                return models
        except Exception as e:
            logger.error(f"Model yapılandırması yüklenemedi {config_path}: {e}")
            return None
    
    def generate_dynamic_script(self, base_script: str, models: List[Dict[str, Any]], 
                              script_version: str = "dynamic") -> str:
        """Model yapılandırmasına göre betik içeriği üretir"""
        try:
            # Model listesinin JavaScript temsili hazırlanır
            models_js = "const MODELS_TO_INJECT = [\n"
            for model in models:
                name = model.get('name', '')
                display_name = model.get('displayName', model.get('display_name', ''))
                description = model.get('description', f'Model injected by script {script_version}')
                
                # displayName içinde sürüm bilgisi yoksa ekle
                if f"(Script {script_version})" not in display_name:
                    display_name = f"{display_name} (Script {script_version})"
                
                models_js += f"""       {{
          name: '{name}',
          displayName: `{display_name}`,
          description: `{description}`
       }},\n"""
            
            models_js += "    ];"
            
            # Betikteki model tanımı bölümünü değiştir
            # Başlangıç ve bitiş işaretlerini bul
            start_marker = "const MODELS_TO_INJECT = ["
            end_marker = "];"
            
            start_idx = base_script.find(start_marker)
            if start_idx == -1:
                logger.error("Model tanımı başlangıç işareti bulunamadı")
                return base_script
                
            # Uygun bitiş işaretini bul
            bracket_count = 0
            end_idx = start_idx + len(start_marker)
            found_end = False
            
            for i in range(end_idx, len(base_script)):
                if base_script[i] == '[':
                    bracket_count += 1
                elif base_script[i] == ']':
                    if bracket_count == 0:
                        end_idx = i + 1
                        found_end = True
                        break
                    bracket_count -= 1
            
            if not found_end:
                logger.error("Model tanımı bitiş işareti bulunamadı")
                return base_script

            # Model tanımı bölümünü değiştir
            new_script = (base_script[:start_idx] + 
                         models_js + 
                         base_script[end_idx:])

            # Sürüm numarasını güncelle
            new_script = new_script.replace(
                f'const SCRIPT_VERSION = "v1.6";',
                f'const SCRIPT_VERSION = "{script_version}";'
            )

            logger.info(f"{len(models)} modeli içeren dinamik betik üretildi")
            return new_script

        except Exception as e:
            logger.error(f"Dinamik betik üretilemedi: {e}")
            return base_script

    async def inject_script_to_page(self, page: AsyncPage, script_content: str, 
                                  script_name: str = "injected_script") -> bool:
        """Betik içeriğini sayfaya enjekte eder"""
        try:
            # Betik doğrudan enjekte edildiği için UserScript başlıklarını kaldır
            cleaned_script = self._clean_userscript_headers(script_content)

            # Betiği enjekte et
            await page.add_init_script(cleaned_script)
            logger.info(f"Betiğin sayfaya enjeksiyonu tamamlandı: {script_name}")
            return True

        except Exception as e:
            logger.error(f"Betiğin sayfaya enjekte edilmesi başarısız {script_name}: {e}")
            return False

    def _clean_userscript_headers(self, script_content: str) -> str:
        """UserScript başlık metnini temizler"""
        lines = script_content.split('\n')
        cleaned_lines = []
        in_userscript_block = False
        
        for line in lines:
            if line.strip().startswith('// ==UserScript=='):
                in_userscript_block = True
                continue
            elif line.strip().startswith('// ==/UserScript=='):
                in_userscript_block = False
                continue
            elif in_userscript_block:
                continue
            else:
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    async def setup_model_injection(self, page: AsyncPage,
                                  script_name: str = "more_modles.js") -> bool:
        """Model enjeksiyonunu yapılandırır - Tampermonkey betiğini doğrudan enjekte eder"""

        # Betik dosyasının varlığını kontrol et
        script_path = os.path.join(self.script_dir, script_name)
        if not os.path.exists(script_path):
            # Betik dosyası yoksa sessizce atla
            return False

        logger.info("Model enjeksiyonunun kurulumu başlatılıyor...")

        # Tampermonkey betiğini yükle
        script_content = self.load_script(script_name)
        if not script_content:
            return False

        # İçeriği değiştirmeden ham betiği enjekte et
        return await self.inject_script_to_page(page, script_content, script_name)


# Global betik yöneticisi örneği
script_manager = ScriptManager()
