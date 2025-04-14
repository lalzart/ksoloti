package axoloti.mcp;

import java.util.ArrayList;
import java.util.List;
import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Represents a complete patch specification from LLM
 */
public class PatchSpecification {
    private String name;
    private String description;
    private List<ObjectSpecification> objects;
    private List<ConnectionSpecification> connections;
    
    public PatchSpecification() {
        this.objects = new ArrayList<>();
        this.connections = new ArrayList<>();
    }
    
    /**
     * Parse a JSON string into a PatchSpecification object
     */
    public static PatchSpecification fromJson(String json) {
        JSONObject jsonObj = new JSONObject(json);
        PatchSpecification spec = new PatchSpecification();
        
        // Basic properties
        spec.setName(jsonObj.optString("name", "Untitled Patch"));
        spec.setDescription(jsonObj.optString("description", ""));
        
        // Parse objects
        JSONArray objectsArray = jsonObj.optJSONArray("objects");
        if (objectsArray != null) {
            for (int i = 0; i < objectsArray.length(); i++) {
                JSONObject objJson = objectsArray.getJSONObject(i);
                ObjectSpecification objSpec = new ObjectSpecification();
                
                objSpec.setId(objJson.getString("id"));
                objSpec.setType(objJson.getString("type"));
                objSpec.setX(objJson.getInt("x"));
                objSpec.setY(objJson.getInt("y"));
                
                // Parse parameters if present
                JSONObject paramsJson = objJson.optJSONObject("parameters");
                if (paramsJson != null) {
                    for (String key : paramsJson.keySet()) {
                        // Convert any value to string to handle various types (int, double, etc.)
                        String paramValue = String.valueOf(paramsJson.get(key));
                        objSpec.addParameter(key, paramValue);
                    }
                }
                
                spec.addObject(objSpec);
            }
        }
        
        // Parse connections
        JSONArray connectionsArray = jsonObj.optJSONArray("connections");
        if (connectionsArray != null) {
            for (int i = 0; i < connectionsArray.length(); i++) {
                JSONObject connJson = connectionsArray.getJSONObject(i);
                ConnectionSpecification connSpec = new ConnectionSpecification();
                
                connSpec.setSourceObjectId(connJson.getString("sourceObjectId"));
                connSpec.setSourceOutlet(connJson.getString("sourceOutlet"));
                connSpec.setDestObjectId(connJson.getString("destObjectId"));
                connSpec.setDestInlet(connJson.getString("destInlet"));
                
                spec.addConnection(connSpec);
            }
        }
        
        return spec;
    }
    
    public String getName() {
        return name;
    }
    
    public void setName(String name) {
        this.name = name;
    }
    
    public String getDescription() {
        return description;
    }
    
    public void setDescription(String description) {
        this.description = description;
    }
    
    public List<ObjectSpecification> getObjects() {
        return objects;
    }
    
    public void setObjects(List<ObjectSpecification> objects) {
        this.objects = objects;
    }
    
    public void addObject(ObjectSpecification object) {
        this.objects.add(object);
    }
    
    public List<ConnectionSpecification> getConnections() {
        return connections;
    }
    
    public void setConnections(List<ConnectionSpecification> connections) {
        this.connections = connections;
    }
    
    public void addConnection(ConnectionSpecification connection) {
        this.connections.add(connection);
    }
} 