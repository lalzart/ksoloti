package axoloti.mcp;

import axoloti.AttributeInstance;
import axoloti.MainFrame;
import axoloti.PatchGUI;
import axoloti.object.AxoObjectAbstract;
import axoloti.object.AxoObjectInstance;
import axoloti.object.AxoObjects;
import axoloti.utils.Constants;

import java.awt.Point;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * A utility class that integrates natural language descriptions to create Gills controls.
 * This tool allows users to describe the controls they want, and the system will
 * automatically create appropriate Gills objects in the patch.
 */
public class GillsIntegrationTool {

    private static final Map<String, String> CONTROL_TYPE_MAPPING = new HashMap<>();
    private static final int POSITION_OFFSET_X = 80;
    private static final int POSITION_OFFSET_Y = 60;
    
    static {
        // Potentiometer related words
        CONTROL_TYPE_MAPPING.put("pot", "pot");
        CONTROL_TYPE_MAPPING.put("potentiometer", "pot");
        CONTROL_TYPE_MAPPING.put("knob", "pot");
        CONTROL_TYPE_MAPPING.put("slider", "pot");
        CONTROL_TYPE_MAPPING.put("dial", "pot");
        
        // Button related words
        CONTROL_TYPE_MAPPING.put("button", "button");
        CONTROL_TYPE_MAPPING.put("switch", "button");
        CONTROL_TYPE_MAPPING.put("trigger", "button");
        
        // LED related words
        CONTROL_TYPE_MAPPING.put("led", "led");
        CONTROL_TYPE_MAPPING.put("light", "led");
        CONTROL_TYPE_MAPPING.put("indicator", "led");
    }
    
    /**
     * Get the Gills object type based on a given keyword.
     *
     * @param keyword The keyword to map to a Gills object type
     * @return The mapped object type or null if not found
     */
    public static String getGillsObjectType(String keyword) {
        return CONTROL_TYPE_MAPPING.get(keyword.toLowerCase());
    }
    
    /**
     * Process a natural language description and add Gills controls to the patch.
     *
     * @param patch The patch to add controls to
     * @param description The natural language description of controls needed
     * @return The number of controls added
     */
    public static int addGillsControlsFromDescription(PatchGUI patch, String description) {
        if (description == null || description.isEmpty()) {
            return 0;
        }
        
        int controlsAdded = 0;
        Point currentPosition = new Point(20, 20);
        
        // Process potentiometers
        controlsAdded += processControlType(patch, description, "pot", currentPosition);
        
        // Process buttons
        currentPosition.x += POSITION_OFFSET_X;
        controlsAdded += processControlType(patch, description, "button", currentPosition);
        
        // Process LEDs
        currentPosition.x += POSITION_OFFSET_X;
        controlsAdded += processControlType(patch, description, "led", currentPosition);
        
        return controlsAdded;
    }
    
    /**
     * Process a specific control type from the description.
     *
     * @param patch The patch to add controls to
     * @param description The natural language description
     * @param controlType The type of control to process
     * @param startPosition The starting position for placement
     * @return The number of controls added
     */
    private static int processControlType(PatchGUI patch, String description, 
                                         String controlType, Point startPosition) {
        int controlsAdded = 0;
        Point currentPosition = new Point(startPosition);
        
        // Find all keywords that map to this control type
        List<String> keywords = new ArrayList<>();
        for (Map.Entry<String, String> entry : CONTROL_TYPE_MAPPING.entrySet()) {
            if (entry.getValue().equals(controlType)) {
                keywords.add(entry.getKey());
            }
        }
        
        // Build regex pattern to find all instances of the keywords followed by "for" and a purpose
        String keywordsPattern = String.join("|", keywords);
        Pattern pattern = Pattern.compile("(" + keywordsPattern + ")\\s+for\\s+(\\w+)", 
                                         Pattern.CASE_INSENSITIVE);
        Matcher matcher = pattern.matcher(description);
        
        // Create a control for each match
        while (matcher.find()) {
            String purpose = matcher.group(2);
            addGillsObject(patch, controlType, purpose, currentPosition);
            currentPosition.y += POSITION_OFFSET_Y;
            controlsAdded++;
        }
        
        return controlsAdded;
    }
    
    /**
     * Add a Gills object to the patch.
     *
     * @param patch The patch to add the object to
     * @param objectType The type of Gills object
     * @param purpose The purpose/name for the control
     * @param position The position to place the object
     * @return The created object instance or null if creation failed
     */
    private static AxoObjectInstance addGillsObject(PatchGUI patch, String objectType, 
                                                  String purpose, Point position) {
        String objectPath = getGillsObjectPath(objectType);
        AxoObjectAbstract objectType1 = AxoObjects.getAxoObjects().getObjectFromPath(objectPath);
        
        if (objectType1 == null) {
            System.err.println("Could not find Gills object: " + objectPath);
            return null;
        }
        
        AxoObjectInstance obj = new AxoObjectInstance(objectType1);
        obj.setName(objectType + "_" + purpose);
        obj.setPos(position.x, position.y);
        
        // Set attributes
        AttributeInstance[] attrs = createGillsAttributes(objectType, purpose);
        obj.setAttributeInstances(attrs);
        
        patch.addObjectInstance(obj);
        patch.repaint();
        
        return obj;
    }
    
    /**
     * Get the object path for a Gills object type.
     *
     * @param objectType The object type (pot, button, led)
     * @return The full path to the object
     */
    private static String getGillsObjectPath(String objectType) {
        if ("led".equals(objectType)) {
            return "gills/out/led";
        } else {
            return "gills/in/" + objectType;
        }
    }
    
    /**
     * Create attribute instances for a Gills object.
     *
     * @param objectType The type of Gills object
     * @param purpose The purpose/name for the control
     * @return Array of attribute instances
     */
    public static AttributeInstance[] createGillsAttributes(String objectType, String purpose) {
        List<AttributeInstance> attributes = new ArrayList<>();
        
        // Common attributes
        AttributeInstance nameAttr = new AttributeInstance("name");
        nameAttr.setValue(purpose);
        attributes.add(nameAttr);
        
        AttributeInstance instAttr = new AttributeInstance("instance");
        instAttr.setValue(objectType + "_" + purpose);
        attributes.add(instAttr);
        
        // Type-specific attributes
        if ("pot".equals(objectType)) {
            AttributeInstance defaultAttr = new AttributeInstance("default");
            defaultAttr.setValue("0");
            attributes.add(defaultAttr);
            
            AttributeInstance minAttr = new AttributeInstance("minimum");
            minAttr.setValue("0");
            attributes.add(minAttr);
        }
        
        return attributes.toArray(new AttributeInstance[0]);
    }
}