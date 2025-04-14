package axoloti.mcp;

import axoloti.MainFrame;
import axoloti.Patch;
import axoloti.PatchGUI;
import axoloti.object.AxoObject;
import axoloti.object.AxoObjectInstance;
import axoloti.object.AxoObjectInstanceAbstract;
import axoloti.object.AxoObjects;
import axoloti.parameters.ParameterInstance;
import java.awt.Point;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;
import org.json.JSONObject;

/**
 * Service for generating Ksoloti patches from natural language descriptions
 */
public class NLPPatchGenerator {
    private static final Logger LOGGER = Logger.getLogger(NLPPatchGenerator.class.getName());
    
    private final LLMService llmService;
    
    public NLPPatchGenerator() {
        // Check if Gemini API key is configured
        if (!LLMServiceGemini.getApiKey().isEmpty()) {
            LOGGER.info("Using Gemini LLM service");
            this.llmService = new LLMServiceGemini();
        } else {
            LOGGER.info("Using mock LLM service (Gemini API key not configured)");
            this.llmService = new LLMServiceMock();
        }
    }
    
    /**
     * Generate a patch from a natural language description
     * 
     * @param description The natural language description
     * @return A new PatchGUI instance with the generated patch
     */
    public PatchGUI generatePatch(String description) {
        try {
            LOGGER.info("Generating patch from description: " + description);
            
            // 1. Use LLM to convert natural language to patch specification
            PatchSpecification spec = convertToPatchSpecification(description);
            
            // 2. Create a new patch (but don't call PostConstructor yet)
            PatchGUI patch = new PatchGUI();
            
            // Don't set filename here - it will be set when the patch frame is created
            // patch.setFileNamePath("generated_" + System.currentTimeMillis());
            
            // 3. Add objects based on the specification
            Map<String, AxoObjectInstanceAbstract> instanceMap = new HashMap<>();
            
            // Process Gills-specific keywords in the description
            boolean hasGillsControls = description.toLowerCase().contains("gills") ||
                                      description.toLowerCase().contains("control") ||
                                      description.toLowerCase().contains("knob") ||
                                      description.toLowerCase().contains("pot") ||
                                      description.toLowerCase().contains("button") ||
                                      description.toLowerCase().contains("led") ||
                                      description.toLowerCase().contains("display");
            
            // Add Gills controls if relevant
            if (hasGillsControls) {
                Map<String, AxoObjectInstanceAbstract> gillsControls = 
                    GillsIntegrationTool.addGillsControlsFromDescription(
                        patch, description, instanceMap, this::findAxoObject);
                
                // Log added controls
                if (!gillsControls.isEmpty()) {
                    LOGGER.info("Added " + gillsControls.size() + " Gills controls to the patch");
                }
            }
            
            // Handle standard objects from the specification
            for (ObjectSpecification objSpec : spec.getObjects()) {
                // Check if this might be a Gills control with a different name
                String objectType = objSpec.getType();
                String gillsType = GillsIntegrationTool.getGillsObjectType(objectType);
                
                if (gillsType != null) {
                    // This is a Gills object, use the proper Gills type
                    LOGGER.info("Converting generic control '" + objectType + "' to Gills-specific type: " + gillsType);
                    objectType = gillsType;
                }
                
                // Find the object in available objects
                AxoObject axoObject = findAxoObject(objectType);
                if (axoObject != null) {
                    // Create instance
                    Point location = new Point(objSpec.getX(), objSpec.getY());
                    AxoObjectInstanceAbstract instance = axoObject.CreateInstance(patch, objSpec.getId(), location);
                    if (patch != null) {
                        patch.objectInstances.add(instance);
                    }
                    instance.PostConstructor();
                    
                    // Store in map for creating connections
                    instanceMap.put(objSpec.getId(), instance);
                    
                    // Set parameters if applicable
                    if (instance instanceof AxoObjectInstance && objSpec.getParameters() != null) {
                        AxoObjectInstance concreteInstance = (AxoObjectInstance) instance;
                        for (Map.Entry<String, String> param : objSpec.getParameters().entrySet()) {
                            // Find parameter - proper value setting requires knowing parameter type
                            // and converting string to appropriate Value object
                            ParameterInstance pi = concreteInstance.GetParameterInstance(param.getKey());
                            if (pi != null) {
                                LOGGER.info("Found parameter: " + param.getKey() + " but setValue requires type conversion");
                                // Value setting is skipped for now as it requires type-specific conversion
                            }
                        }
                    }
                    
                    // If this is a Gills object, set attributes based on convention
                    if (objectType.startsWith("ksoloti/gills/")) {
                        applyGillsAttributes(instance, objSpec);
                    }
                } else {
                    LOGGER.warning("Could not find object of type: " + objSpec.getType());
                }
            }
            
            // 4. Create connections
            for (ConnectionSpecification connSpec : spec.getConnections()) {
                AxoObjectInstanceAbstract sourceObj = instanceMap.get(connSpec.getSourceObjectId());
                AxoObjectInstanceAbstract destObj = instanceMap.get(connSpec.getDestObjectId());
                
                if (sourceObj != null && destObj != null) {
                    // Try to connect the objects
                    if (sourceObj.GetOutletInstance(connSpec.getSourceOutlet()) != null && 
                        destObj.GetInletInstance(connSpec.getDestInlet()) != null) {
                        patch.AddConnection(
                            destObj.GetInletInstance(connSpec.getDestInlet()),
                            sourceObj.GetOutletInstance(connSpec.getSourceOutlet())
                        );
                    } else {
                        LOGGER.warning("Could not create connection: " + 
                            connSpec.getSourceObjectId() + "." + connSpec.getSourceOutlet() + " -> " +
                            connSpec.getDestObjectId() + "." + connSpec.getDestInlet());
                    }
                }
            }
            
            // Add auto-connections from Gills controls if no explicit connections
            if (hasGillsControls) {
                connectGillsControlsToModules(patch, instanceMap);
            }
            
            // Don't call PostContructor here - it needs a PatchFrame
            // Let the caller call it after creating the PatchFrame
            
            // Set display name in notes field via reflection (since it's not public)
            if (spec.getName() != null && !spec.getName().isEmpty()) {
                String notes = "Generated patch: " + spec.getName();
                if (spec.getDescription() != null && !spec.getDescription().isEmpty()) {
                    notes += "\n\n" + spec.getDescription();
                }
                
                // Add note about Gills controls if they were added
                if (hasGillsControls) {
                    notes += "\n\nThis patch uses Ksoloti Gills hardware controls.";
                }
                
                try {
                    java.lang.reflect.Field notesField = Patch.class.getDeclaredField("notes");
                    notesField.setAccessible(true);
                    notesField.set(patch, notes);
                } catch (Exception e) {
                    LOGGER.log(Level.WARNING, "Could not set patch notes", e);
                }
            }
            
            return patch;
        } catch (Exception e) {
            LOGGER.log(Level.SEVERE, "Error generating patch", e);
            throw new RuntimeException("Failed to generate patch: " + e.getMessage(), e);
        }
    }
    
    /**
     * Apply appropriate attributes to Gills objects based on their ID and type
     */
    private void applyGillsAttributes(AxoObjectInstanceAbstract instance, ObjectSpecification objSpec) {
        if (!(instance instanceof AxoObjectInstance)) {
            return;
        }
        
        AxoObjectInstance concreteInstance = (AxoObjectInstance) instance;
        String id = objSpec.getId();
        String type = objSpec.getType();
        
        // Extract number from the ID if present
        int number = 1;
        if (id.matches(".*\\d+.*")) {
            try {
                number = Integer.parseInt(id.replaceAll("\\D+", ""));
            } catch (NumberFormatException e) {
                // Use default number 1
            }
        }
        
        // Apply attributes based on the type of Gills object
        Map<String, String> attributes = GillsIntegrationTool.createGillsAttributes(type, number);
        for (Map.Entry<String, String> attr : attributes.entrySet()) {
            // Instead of trying to set attributes directly, we'll just log that we would set attributes
            LOGGER.info("Would set attribute " + attr.getKey() + " to " + attr.getValue() + " for " + concreteInstance.getInstanceName());
        }
    }
    
    /**
     * Connect Gills controls to appropriate modules in the patch
     * This performs intelligent auto-connections when explicit connections aren't specified
     */
    private void connectGillsControlsToModules(PatchGUI patch, Map<String, AxoObjectInstanceAbstract> instanceMap) {
        // Group objects by type
        Map<String, List<AxoObjectInstanceAbstract>> objectsByType = new HashMap<>();
        
        for (Map.Entry<String, AxoObjectInstanceAbstract> entry : instanceMap.entrySet()) {
            String objectId = entry.getKey();
            AxoObjectInstanceAbstract instance = entry.getValue();
            
            // Get object type information safely
            String objectType = "unknown";
            if (instance.getType() != null) {
                objectType = instance.getType().toString();
            }
            
            if (!objectsByType.containsKey(objectType)) {
                objectsByType.put(objectType, new ArrayList<>());
            }
            objectsByType.get(objectType).add(instance);
        }
        
        // Handle pot connections to parameters
        if (objectsByType.containsKey("ksoloti/gills/pot p") && objectsByType.containsKey("osc/sine")) {
            // Example: Connect the first pot to the first oscillator's pitch
            AxoObjectInstanceAbstract pot = objectsByType.get("ksoloti/gills/pot p").get(0);
            AxoObjectInstanceAbstract osc = objectsByType.get("osc/sine").get(0);
            
            if (pot.GetOutletInstance("out") != null && osc.GetInletInstance("pitch") != null) {
                patch.AddConnection(
                    osc.GetInletInstance("pitch"),
                    pot.GetOutletInstance("out")
                );
                LOGGER.info("Auto-connected pot to oscillator pitch");
            }
        }
        
        // Handle additional auto-connections based on what objects are available
        // This is a simplified example - a real implementation would be more extensive
    }
    
    /**
     * Convert natural language to a structured patch specification
     */
    private PatchSpecification convertToPatchSpecification(String description) {
        try {
            // Update the prompt to include Gills if mentioned
            String enhancedPrompt = description;
            if (description.toLowerCase().contains("gills") || 
                description.toLowerCase().contains("control") ||
                description.toLowerCase().contains("knob") ||
                description.toLowerCase().contains("pot")) {
                enhancedPrompt = "Use Ksoloti Gills controller hardware for: " + description;
            }
            
            // Call LLM service to get JSON specification
            String jsonSpec = llmService.generatePatchSpecification(enhancedPrompt);
            
            // Parse the JSON into our specification object
            return PatchSpecification.fromJson(jsonSpec);
        } catch (Exception e) {
            LOGGER.log(Level.SEVERE, "Error converting description to specification", e);
            throw new RuntimeException("Failed to convert description to specification", e);
        }
    }
    
    /**
     * Find an AxoObject by type name
     */
    private AxoObject findAxoObject(String typeName) {
        AxoObjects axoObjects = MainFrame.axoObjects;
        if (axoObjects != null) {
            ArrayList<AxoObject> matches = new ArrayList<>();
            
            // Search through all objects
            for (Object obj : axoObjects.ObjectList) {
                if (obj instanceof AxoObject) {
                    AxoObject axoObj = (AxoObject) obj;
                    if (axoObj.id.equals(typeName)) {
                        matches.add(axoObj);
                    }
                }
            }
            
            // Return the first match or null if none
            return matches.isEmpty() ? null : matches.get(0);
        }
        return null;
    }
} 