package axoloti.mcp;

import org.json.JSONArray;
import org.json.JSONObject;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.prefs.Preferences;

/**
 * Implementation of LLMService that uses Google's Gemini API
 */
public class LLMServiceGemini implements LLMService {
    private static final Logger LOGGER = Logger.getLogger(LLMServiceGemini.class.getName());
    private static final String API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent";
    private static final String PREFS_KEY = "gemini_api_key";
    
    private String apiKey;
    
    public LLMServiceGemini() {
        // Load API key from preferences
        loadApiKey();
    }
    
    private void loadApiKey() {
        Preferences prefs = Preferences.userNodeForPackage(LLMServiceGemini.class);
        apiKey = prefs.get(PREFS_KEY, "");
    }
    
    public static void saveApiKey(String key) {
        Preferences prefs = Preferences.userNodeForPackage(LLMServiceGemini.class);
        prefs.put(PREFS_KEY, key);
    }
    
    public static String getApiKey() {
        Preferences prefs = Preferences.userNodeForPackage(LLMServiceGemini.class);
        return prefs.get(PREFS_KEY, "");
    }
    
    public boolean hasApiKey() {
        return apiKey != null && !apiKey.trim().isEmpty();
    }
    
    @Override
    public String generatePatchSpecification(String description) {
        if (!hasApiKey()) {
            LOGGER.warning("No Gemini API key configured");
            throw new RuntimeException("Gemini API key not configured. Please set your API key in the settings.");
        }
        
        try {
            LOGGER.info("Generating patch specification from description using Gemini API");
            
            // Create connection
            URL url = new URL(API_URL + "?key=" + apiKey);
            HttpURLConnection connection = (HttpURLConnection) url.openConnection();
            connection.setRequestMethod("POST");
            connection.setRequestProperty("Content-Type", "application/json");
            connection.setDoOutput(true);
            
            // Check if the description includes Gills-related keywords
            boolean useGills = description.toLowerCase().contains("gills") || 
                              description.toLowerCase().contains("using ksoloti gills") ||
                              description.toLowerCase().contains("use ksoloti gills");
            
            // Create the prompt with specific instructions for generating a patch specification
            String promptText = "You are a patch generator for a modular synthesizer called Ksoloti/Axoloti. " +
                    "Create a complete patch based on this description: \"" + description + "\"\n\n" +
                    "Return ONLY a valid JSON object with the following structure:\n" +
                    "{\n" +
                    "  \"name\": \"Patch name\",\n" +
                    "  \"description\": \"Short description of the patch\",\n" +
                    "  \"objects\": [\n" +
                    "    {\n" +
                    "      \"id\": \"unique_id\",\n" +
                    "      \"type\": \"category/object_type\",\n" +
                    "      \"x\": x_position,\n" +
                    "      \"y\": y_position,\n" +
                    "      \"parameters\": { \"param_name\": \"value\" }\n" +
                    "    }\n" +
                    "  ],\n" +
                    "  \"connections\": [\n" +
                    "    {\n" +
                    "      \"sourceObjectId\": \"source_id\",\n" +
                    "      \"sourceOutlet\": \"outlet_name\",\n" +
                    "      \"destObjectId\": \"dest_id\",\n" +
                    "      \"destInlet\": \"inlet_name\"\n" +
                    "    }\n" +
                    "  ]\n" +
                    "}\n\n" +
                    "Common object types include: osc/sine, osc/saw, osc/square, osc/tri, noise/pink, noise/white, " +
                    "filter/lp, filter/hp, filter/bp, gain/vca, envelope/adsr, delay/stereo, reverb/plate, " +
                    "audio/out stereo, mix/stereo 2, midi/in, pulse/bpm, logic/counter";
            
            // Add Gills-specific information if relevant
            if (useGills) {
                promptText += "\n\nThe Ksoloti Gills hardware expansion provides physical controls that should be used in the patch:\n" +
                        "- ksoloti/gills/pot p - Unipolar potentiometer (values 0-64), 10 available (numbered 1-10)\n" +
                        "- ksoloti/gills/pot b - Bipolar potentiometer (values -64 to 64), 10 available (numbered 1-10)\n" +
                        "- ksoloti/gills/button - Pushbutton, 4 available (numbered 1-4)\n" +
                        "- ksoloti/gills/led - LED indicator, 4 available (LED 1-2 single color, LED 3-4 dual color)\n" +
                        "- ksoloti/gills/encoder - Rotary encoder with button\n" +
                        "- ksoloti/gills/display - OLED display for showing text and waveforms\n" +
                        "- ksoloti/gills/cv out p - CV output (unipolar), 2 available (CV1, CV2)\n" +
                        "- ksoloti/gills/cv out b - CV output (bipolar), 2 available (CV1, CV2)\n\n" +
                        "Connect these physical controls to appropriate parameters of the synth modules.";
            }
            
            // Prepare request payload
            JSONObject requestBody = new JSONObject();
            JSONArray contents = new JSONArray();
            JSONObject content = new JSONObject();
            JSONArray parts = new JSONArray();
            JSONObject part = new JSONObject();
            
            part.put("text", promptText);
            parts.put(part);
            content.put("parts", parts);
            contents.put(content);
            requestBody.put("contents", contents);
            
            // Enable proper JSON response
            JSONObject generationConfig = new JSONObject();
            generationConfig.put("temperature", 0.2);
            generationConfig.put("topK", 40);
            generationConfig.put("topP", 0.95);
            requestBody.put("generationConfig", generationConfig);
            
            // Write request
            try (OutputStream os = connection.getOutputStream()) {
                byte[] input = requestBody.toString().getBytes(StandardCharsets.UTF_8);
                os.write(input, 0, input.length);
            }
            
            // Get response
            int responseCode = connection.getResponseCode();
            if (responseCode == HttpURLConnection.HTTP_OK) {
                try (BufferedReader br = new BufferedReader(
                        new InputStreamReader(connection.getInputStream(), StandardCharsets.UTF_8))) {
                    StringBuilder response = new StringBuilder();
                    String responseLine;
                    while ((responseLine = br.readLine()) != null) {
                        response.append(responseLine.trim());
                    }
                    
                    // Parse response to extract generated content
                    String jsonResponse = response.toString();
                    JSONObject jsonObj = new JSONObject(jsonResponse);
                    String generatedText = extractGeneratedText(jsonObj);
                    
                    // Extract just the JSON object from the response
                    return extractJsonFromText(generatedText);
                }
            } else {
                try (BufferedReader br = new BufferedReader(
                        new InputStreamReader(connection.getErrorStream(), StandardCharsets.UTF_8))) {
                    StringBuilder response = new StringBuilder();
                    String responseLine;
                    while ((responseLine = br.readLine()) != null) {
                        response.append(responseLine.trim());
                    }
                    LOGGER.severe("Gemini API error: " + response.toString());
                }
                
                throw new RuntimeException("Failed to get response from Gemini API, status code: " + responseCode);
            }
        } catch (Exception e) {
            LOGGER.log(Level.SEVERE, "Error calling Gemini API", e);
            throw new RuntimeException("Failed to generate patch: " + e.getMessage(), e);
        }
    }
    
    private String extractGeneratedText(JSONObject response) {
        try {
            return response.getJSONArray("candidates")
                .getJSONObject(0)
                .getJSONObject("content")
                .getJSONArray("parts")
                .getJSONObject(0)
                .getString("text");
        } catch (Exception e) {
            LOGGER.log(Level.SEVERE, "Error extracting text from Gemini response", e);
            throw new RuntimeException("Failed to parse Gemini API response", e);
        }
    }
    
    private String extractJsonFromText(String text) {
        // Find the first { and the last } to extract the JSON object
        int start = text.indexOf('{');
        int end = text.lastIndexOf('}') + 1;
        
        if (start != -1 && end != -1 && end > start) {
            return text.substring(start, end);
        }
        
        // If no JSON object is found, return the entire text
        // This will likely cause a JSON parsing error later, which is handled
        return text;
    }
} 